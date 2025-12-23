import socket
import threading
from datetime import datetime
import queue
import time
import random
import streamlit as st
import ssl
from udp_crypto import UDPCrypto

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5555, protocol='TCP', use_ssl=True):
        self.host = host
        self.port = port
        self.protocol = protocol.upper()
        self.use_ssl = use_ssl
        self.server = None
        self.running = False
        self.log_queue = queue.Queue()
        self.clients_queue = queue.Queue()
        
        # SSL context for TCP
        self.ssl_context = None
        if self.use_ssl and self.protocol == 'TCP':
            try:
                self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                self.ssl_context.load_cert_chain('server.cert', 'server.key')
                self.log("🔐 SSL certificates loaded successfully", "SUCCESS")
            except Exception as e:
                self.log(f"⚠️ SSL initialization failed: {e}. Running without encryption.", "WARNING")
                self.use_ssl = False
        
        # UDP Encryption
        self.udp_crypto = None
        if self.use_ssl and self.protocol == 'UDP':
            try:
                self.udp_crypto = UDPCrypto()
                self.log("🔐 UDP Encryption initialized successfully (AES-256-GCM)", "SUCCESS")
            except Exception as e:
                self.log(f"⚠️ UDP encryption initialization failed: {e}. Running without encryption.", "WARNING")
                self.use_ssl = False
        
        # Stockage des conversations par client
        self.conversations = {}
        self.conversations_queue = queue.Queue()

        # Reliability tracking
        self.message_id_counter = 0
        self.pending_acks = {}
        self.received_msg_ids = {}
        self.lock = threading.Lock()
        
        # Statistics per client
        self.client_stats = {}

        if self.protocol == 'TCP':
            self.clients = []
            self.nicknames = []
            self.client_map = {}
        else:
            self.clients = {}
            self.client_map = {}
            self.addr_to_nickname = {}

        # UDP Configuration
        self.ack_timeout = 2.0
        self.max_retries = 5
        self.packet_loss_rate = 0.30

    def simulate_packet_loss(self):
        """Simule la perte de paquets selon le taux configuré"""
        if self.protocol == 'UDP':
            return random.random() < self.packet_loss_rate
        return False

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put({"time": timestamp, "level": level, "message": message})

    def update_clients_list(self):
        if self.protocol == 'TCP':
            self.clients_queue.put(self.nicknames.copy())
        else:
            self.clients_queue.put(list(self.clients.values()))

    def add_to_conversation(self, nickname, message, is_server=False):
        """Ajoute un message à la conversation d'un client"""
        if nickname not in self.conversations:
            self.conversations[nickname] = []
        
        timestamp = datetime.now().strftime("%H:%M")
        self.conversations[nickname].append({
            'time': timestamp,
            'text': message,
            'is_server': is_server
        })
        
        # Notifier l'interface
        self.conversations_queue.put({
            'nickname': nickname,
            'message': {
                'time': timestamp,
                'text': message,
                'is_server': is_server
            }
        })

    def init_client_stats(self, nickname):
        """Initialize statistics for a client"""
        self.client_stats[nickname] = {
            'sent_count': 0,
            'received_count': 0,
            'ack_count': 0,
            'retransmissions': 0,
            'packet_loss': 0,
            'duplicates': 0,
            'latency_samples': [],
            'simulated_drops': 0,
            'encrypted_messages': 0
        }

    def send_to_client(self, nickname, message):
        """Envoie un message à un client spécifique"""
        full_msg = f"[SERVER]: {message}"
        send_time = time.time()
        
        try:
            if self.protocol == 'TCP':
                if nickname in self.client_map:
                    client = self.client_map[nickname]
                    tcp_msg = f"{full_msg}|TS:{send_time}|"
                    
                    # Log encryption status
                    if self.use_ssl:
                        self.log(f"🔒 Encrypting message for {nickname}", "INFO")
                    
                    client.send(tcp_msg.encode('utf-8'))
                    
                    if self.use_ssl:
                        self.log(f"✅ Encrypted message sent to {nickname}", "SUCCESS")
                    else:
                        self.log(f"Server → {nickname}: {message}", "SUCCESS")
                    
                    self.add_to_conversation(nickname, message, is_server=True)
                    
                    with self.lock:
                        if nickname in self.client_stats:
                            self.client_stats[nickname]['sent_count'] += 1
                            if self.use_ssl:
                                self.client_stats[nickname]['encrypted_messages'] += 1
                    return True
            else:
                # UDP with reliability and encryption
                if nickname in self.client_map:
                    addr = self.client_map[nickname]
                    
                    with self.lock:
                        msg_id = self.message_id_counter
                        self.message_id_counter += 1
                        if nickname in self.client_stats:
                            self.client_stats[nickname]['sent_count'] += 1
                            if self.use_ssl and self.udp_crypto:
                                self.client_stats[nickname]['encrypted_messages'] += 1
                    
                    udp_msg = f"MSG:{msg_id}:{send_time}:{full_msg}"
                    
                    # Encrypt if UDP encryption is enabled
                    if self.use_ssl and self.udp_crypto:
                        try:
                            udp_msg = self.udp_crypto.encrypt_message(udp_msg)
                            self.log(f"🔒 Encrypting UDP message for {nickname}", "INFO")
                        except Exception as e:
                            self.log(f"⚠️ Encryption failed: {e}. Sending unencrypted.", "WARNING")
                    
                    data = udp_msg.encode('utf-8')
                    
                    if not self.simulate_packet_loss():
                        self.server.sendto(data, addr)
                    else:
                        with self.lock:
                            if nickname in self.client_stats:
                                self.client_stats[nickname]['simulated_drops'] += 1
                        self.log(f"[SIMULATED DROP] Server → {nickname}", "WARNING")
                    
                    with self.lock:
                        self.pending_acks[(addr, msg_id)] = {
                            'data': data,
                            'timestamp': send_time,
                            'retries': 0,
                            'nickname': nickname
                        }
                    
                    if self.use_ssl and self.udp_crypto:
                        self.log(f"✅ Encrypted message sent to {nickname}", "SUCCESS")
                    else:
                        self.log(f"Server → {nickname}: {message}", "SUCCESS")
                    
                    self.add_to_conversation(nickname, message, is_server=True)
                    return True
            return False
        except Exception as e:
            self.log(f"Failed to send message to {nickname}: {e}", "ERROR")
            return False

    def handle_client_tcp(self, client, nickname):
        while self.running:
            try:
                data = client.recv(2048)
                if not data:
                    self.remove_client_tcp(client)
                    break
                
                msg = data.decode('utf-8').strip()
                if not msg:
                    continue
                
                # Log decryption
                if self.use_ssl:
                    self.log(f"🔓 Decrypted message from {nickname}", "INFO")
                
                receive_time = time.time()
                latency = None
                
                if '|TS:' in msg:
                    parts = msg.split('|TS:')
                    msg = parts[0]
                    if len(parts) >= 2:
                        try:
                            send_time = float(parts[1].split('|')[0])
                            latency = (receive_time - send_time) * 1000
                        except:
                            pass
                
                if msg.startswith(nickname + ': '):
                    clean_msg = msg.replace(nickname + ': ', '', 1)
                else:
                    clean_msg = msg
                
                with self.lock:
                    if nickname in self.client_stats:
                        self.client_stats[nickname]['received_count'] += 1
                        if self.use_ssl:
                            self.client_stats[nickname]['encrypted_messages'] += 1
                        if latency:
                            self.client_stats[nickname]['latency_samples'].append(latency)
                            if len(self.client_stats[nickname]['latency_samples']) > 100:
                                self.client_stats[nickname]['latency_samples'] = \
                                    self.client_stats[nickname]['latency_samples'][-100:]
                
                self.log(f"{nickname}: {clean_msg}", "MESSAGE")
                self.add_to_conversation(nickname, clean_msg, is_server=False)
                
            except:
                if self.running:
                    self.remove_client_tcp(client)
                break

    def accept_connections_tcp(self):
        while self.running:
            try:
                self.server.settimeout(3.0)
                client, addr = self.server.accept()
                self.log(f"Connection from {addr[0]}:{addr[1]}", "INFO")

                # Wrap socket with SSL if enabled
                if self.use_ssl and self.ssl_context:
                    try:
                        client = self.ssl_context.wrap_socket(client, server_side=True)
                        self.log(f"🔐 SSL handshake completed with {addr[0]}:{addr[1]}", "SUCCESS")
                    except Exception as e:
                        self.log(f"❌ SSL handshake failed: {e}", "ERROR")
                        client.close()
                        continue

                client.send("NICK".encode('utf-8'))
                nickname = client.recv(1024).decode('utf-8').strip()
                
                self.clients.append(client)
                self.nicknames.append(nickname)
                self.client_map[nickname] = client
                self.conversations[nickname] = []
                self.init_client_stats(nickname)
                
                if self.use_ssl:
                    self.log(f"🔒 {nickname} connected with SSL encryption", "SUCCESS")
                else:
                    self.log(f"{nickname} connected successfully", "SUCCESS")
                
                self.update_clients_list()
                
                welcome_msg = f"Connected to server! {'🔒 SSL Encryption enabled.' if self.use_ssl else ''} You can now chat with the server.|TS:{time.time()}|"
                client.send(welcome_msg.encode('utf-8'))

                threading.Thread(target=self.handle_client_tcp, args=(client, nickname), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log(f"TCP Accept Error: {e}", "ERROR")

    def remove_client_tcp(self, client):
        if client in self.clients:
            idx = self.clients.index(client)
            nickname = self.nicknames[idx]
            self.clients.remove(client)
            self.nicknames.remove(nickname)
            if nickname in self.client_map:
                del self.client_map[nickname]
            if nickname in self.client_stats:
                del self.client_stats[nickname]
            self.log(f"{nickname} disconnected", "WARNING")
            self.update_clients_list()
            try:
                client.close()
            except:
                pass

    def handle_messages_udp(self):
        while self.running:
            try:
                self.server.settimeout(1.0)
                data, addr = self.server.recvfrom(2048)
                msg = data.decode('utf-8')
                
                # Try to decrypt if encryption is enabled
                if self.use_ssl and self.udp_crypto and msg.startswith('ENC:'):
                    try:
                        msg = self.udp_crypto.decrypt_message(msg)
                        self.log(f"🔓 Decrypted UDP message from {addr[0]}:{addr[1]}", "INFO")
                    except Exception as e:
                        self.log(f"⚠️ Failed to decrypt message: {e}", "ERROR")
                        continue

                # Handle DISCONNECT messages
                if msg.startswith('DISCONNECT:'):
                    nickname = msg.split(':', 1)[1]
                    self.log(f"📩 Received DISCONNECT from {nickname} at {addr[0]}:{addr[1]}", "INFO")
                    
                    is_connected = False
                    with self.lock:
                        is_connected = addr in self.clients
                    
                    if is_connected:
                        self.remove_client_udp(addr)
                    else:
                        self.log(f"⚠️ DISCONNECT for unknown address {addr[0]}:{addr[1]}", "WARNING")
                    continue

                # Handle NEW connections
                client_exists = False
                with self.lock:
                    client_exists = addr in self.clients
                
                if not client_exists:
                    nickname = msg.strip()
                    
                    with self.lock:
                        self.clients[addr] = nickname
                        self.client_map[nickname] = addr
                        self.addr_to_nickname[addr] = nickname
                        self.received_msg_ids[addr] = set()
                    
                    self.conversations[nickname] = []
                    self.init_client_stats(nickname)
                    
                    encryption_status = "with AES-256-GCM encryption" if (self.use_ssl and self.udp_crypto) else "No encryption"
                    self.log(f"✅ {nickname} connected from {addr[0]}:{addr[1]} (UDP - {encryption_status})", "SUCCESS")
                    self.update_clients_list()
                    
                    welcome_msg = f"Connected to server! {'🔒 UDP Encryption enabled (AES-256-GCM)' if (self.use_ssl and self.udp_crypto) else '(UDP mode - no encryption)'}"
                    with self.lock:
                        msg_id = self.message_id_counter
                        self.message_id_counter += 1
                    welcome_full = f"MSG:{msg_id}:{time.time()}:{welcome_msg}"
                    
                    # Encrypt welcome message if encryption enabled
                    if self.use_ssl and self.udp_crypto:
                        try:
                            welcome_full = self.udp_crypto.encrypt_message(welcome_full)
                        except:
                            pass
                    
                    if not self.simulate_packet_loss():
                        self.server.sendto(welcome_full.encode('utf-8'), addr)
                    else:
                        with self.lock:
                            if nickname in self.client_stats:
                                self.client_stats[nickname]['simulated_drops'] += 1
                        self.log(f"[SIMULATED DROP] Welcome message to {nickname}", "WARNING")
                    continue

                # Handle ACK messages
                if msg.startswith('ACK:'):
                    if self.simulate_packet_loss():
                        with self.lock:
                            nickname = self.addr_to_nickname.get(addr, "Unknown")
                            if nickname != "Unknown" and nickname in self.client_stats:
                                self.client_stats[nickname]['simulated_drops'] += 1
                        self.log(f"[SIMULATED DROP] ACK from {nickname}", "WARNING")
                        continue
                        
                    try:
                        msg_id = int(msg.split(':')[1])
                        with self.lock:
                            key = (addr, msg_id)
                            if key in self.pending_acks: #wsal ack meaning nemhi pending
                                nickname = self.pending_acks[key]['nickname']
                                send_time = self.pending_acks[key]['timestamp']
                                latency = (time.time() - send_time) * 1000
                                
                                if nickname in self.client_stats:
                                    self.client_stats[nickname]['ack_count'] += 1
                                    self.client_stats[nickname]['latency_samples'].append(latency)
                                    if len(self.client_stats[nickname]['latency_samples']) > 100:
                                        self.client_stats[nickname]['latency_samples'] = \
                                            self.client_stats[nickname]['latency_samples'][-100:]
                                
                                del self.pending_acks[key]
                    except Exception as e:
                        self.log(f"Error processing ACK: {e}", "ERROR")
                    continue

                # Handle MSG messages
                if msg.startswith('MSG:'):
                    if self.simulate_packet_loss():
                        with self.lock:
                            nickname = self.clients.get(addr, "Unknown")
                            if nickname != "Unknown" and nickname in self.client_stats:
                                self.client_stats[nickname]['simulated_drops'] += 1
                        self.log(f"[SIMULATED DROP] Message from {nickname}", "WARNING")
                        continue
                    
                    parts = msg.split(':', 3)
                    if len(parts) >= 4:
                        msg_id = int(parts[1])
                        send_time = float(parts[2])
                        actual_msg = parts[3]
                        
                        nickname = None
                        with self.lock:
                            nickname = self.clients.get(addr)
                        
                        if not nickname:
                            self.log(f"⚠️ Received message from unknown address {addr[0]}:{addr[1]}", "WARNING")
                            continue
                        
                        receive_time = time.time()
                        latency = (receive_time - send_time) * 1000
                        
                        is_duplicate = False
                        with self.lock:
                            if addr not in self.received_msg_ids:
                                self.received_msg_ids[addr] = set()
                            
                            if msg_id in self.received_msg_ids[addr]:
                                is_duplicate = True
                                if nickname in self.client_stats:
                                    self.client_stats[nickname]['duplicates'] += 1
                            else:
                                self.received_msg_ids[addr].add(msg_id)
                        
                        ack_data = f"ACK:{msg_id}"
                        
                        # Encrypt ACK if encryption enabled
                        if self.use_ssl and self.udp_crypto:
                            try:
                                ack_data = self.udp_crypto.encrypt_message(ack_data)
                            except:
                                pass
                        
                        if not self.simulate_packet_loss():
                            self.server.sendto(ack_data.encode('utf-8'), addr)
                        else:
                            with self.lock:
                                if nickname in self.client_stats:
                                    self.client_stats[nickname]['simulated_drops'] += 1
                            self.log(f"[SIMULATED DROP] ACK to {nickname}", "WARNING")
                        
                        if is_duplicate:
                            continue
                        
                        if actual_msg.startswith(nickname + ": "):
                            clean_msg = actual_msg.replace(nickname + ": ", "", 1)
                        else:
                            clean_msg = actual_msg
                        
                        with self.lock:
                            if nickname in self.client_stats:
                                self.client_stats[nickname]['received_count'] += 1
                                if self.use_ssl and self.udp_crypto:
                                    self.client_stats[nickname]['encrypted_messages'] += 1
                                self.client_stats[nickname]['latency_samples'].append(latency)
                                if len(self.client_stats[nickname]['latency_samples']) > 100:
                                    self.client_stats[nickname]['latency_samples'] = \
                                        self.client_stats[nickname]['latency_samples'][-100:]
                        
                        self.log(f"{nickname}: {clean_msg}", "MESSAGE")
                        self.add_to_conversation(nickname, clean_msg, is_server=False)
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log(f"❌ UDP Handler Error: {e}", "ERROR")

    def retransmit_pending_udp(self):
        """Retransmit messages - disconnect ONLY the specific failing client"""
        while self.running:
            try:
                time.sleep(0.1)
                current_time = time.time()
                
                messages_to_check = []
                with self.lock:
                    for key, data in list(self.pending_acks.items()):
                        addr, msg_id = key
                        if addr in self.clients:
                            messages_to_check.append((
                                addr,
                                msg_id,
                                data['data'],
                                data['timestamp'],
                                data['retries'],
                                data['nickname']
                            ))
                
                to_retransmit = []
                clients_to_disconnect = {}
                
                for addr, msg_id, data, timestamp, retries, nickname in messages_to_check:
                    elapsed = current_time - timestamp
                    
                    if elapsed > self.ack_timeout:
                        if retries < self.max_retries:
                            to_retransmit.append((addr, msg_id, data, nickname))
                        else:
                            clients_to_disconnect[addr] = nickname
                            self.log(f"⚠️ Client {nickname} ({addr[0]}:{addr[1]}) will be disconnected after {self.max_retries} failed retries", "ERROR")

                if clients_to_disconnect:
                    with self.lock:
                        for addr, nickname in clients_to_disconnect.items():
                            if nickname in self.client_stats:
                                failed_count = sum(1 for a, m, d, t, r, n in messages_to_check 
                                                 if a == addr and (current_time - t) > self.ack_timeout and r >= self.max_retries)
                                self.client_stats[nickname]['packet_loss'] += failed_count
                            
                            keys_to_remove = [k for k in list(self.pending_acks.keys()) if k[0] == addr]
                            for k in keys_to_remove:
                                if k in self.pending_acks:
                                    del self.pending_acks[k]
                
                for addr, msg_id, data, nickname in to_retransmit:
                    if addr in clients_to_disconnect:
                        continue
                        
                    client_exists = False
                    with self.lock:
                        client_exists = addr in self.clients
                    
                    if not client_exists:
                        continue
                    
                    try:
                        if not self.simulate_packet_loss():
                            self.server.sendto(data, addr)
                        else:
                            with self.lock:
                                if nickname in self.client_stats:
                                    self.client_stats[nickname]['simulated_drops'] += 1
                            self.log(f"[SIMULATED DROP] Retransmit to {nickname}", "WARNING")
                        
                        with self.lock:
                            key = (addr, msg_id)
                            if key in self.pending_acks:
                                self.pending_acks[key]['timestamp'] = time.time()
                                self.pending_acks[key]['retries'] += 1
                                if nickname in self.client_stats:
                                    self.client_stats[nickname]['retransmissions'] += 1
                    except Exception as e:
                        self.log(f"Retransmit error for {nickname}: {e}", "ERROR")
                        clients_to_disconnect[addr] = nickname

                for addr, nickname in clients_to_disconnect.items():
                    client_exists = False
                    with self.lock:
                        client_exists = addr in self.clients
                    
                    if client_exists:
                        self.log(f"🔴 DISCONNECTING {nickname} at {addr[0]}:{addr[1]} due to packet loss", "ERROR")
                        self.remove_client_udp(addr)
                        self.log(f"✅ Successfully removed {nickname}. Remaining clients: {len(self.clients)}", "INFO")

            except Exception as e:
                if self.running:
                    self.log(f"❌ Retransmit thread error: {e}", "ERROR")
                time.sleep(0.5)

    def remove_client_udp(self, addr):
        """Remove a specific UDP client by address"""
        nickname = None
        
        with self.lock:
            if addr not in self.clients:
                self.log(f"⚠️ Attempted to remove non-existent client at {addr[0]}:{addr[1]}", "WARNING")
                return
            
            nickname = self.clients[addr]
            self.log(f"🔄 Starting removal of {nickname} at {addr[0]}:{addr[1]}", "INFO")
            
            clients_before = len(self.clients)
            
            if addr in self.clients:
                del self.clients[addr]
            
            if nickname in self.client_map:
                del self.client_map[nickname]
            
            if addr in self.addr_to_nickname:
                del self.addr_to_nickname[addr]
            
            if nickname in self.client_stats:
                del self.client_stats[nickname]
            
            if addr in self.received_msg_ids:
                del self.received_msg_ids[addr]
            
            clients_after = len(self.clients)
            remaining = list(self.clients.values())
        
        if nickname:
            self.log(f"✅ Removed {nickname} ({addr[0]}:{addr[1]}). Clients: {clients_before} → {clients_after}", "WARNING")
            if remaining:
                self.log(f"📋 Remaining clients: {', '.join(remaining)}", "INFO")
            else:
                self.log(f"📋 No clients remaining", "INFO")
            self.update_clients_list()

    def start(self):
        try:
            if self.protocol == 'TCP':
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.clients = []
                self.nicknames = []
                self.client_map = {}
                self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server.bind((self.host, self.port))
                self.server.listen()
                self.running = True
                
                if self.use_ssl:
                    self.log(f"🔒 TCP Server started with SSL on {self.host}:{self.port}", "SUCCESS")
                else:
                    self.log(f"TCP Server started on {self.host}:{self.port}", "SUCCESS")
                
                threading.Thread(target=self.accept_connections_tcp, daemon=True).start()
            else:
                self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.clients = {}
                self.client_map = {}
                self.addr_to_nickname = {}
                self.received_msg_ids = {}
                self.server.bind((self.host, self.port))
                self.running = True
                
                if self.use_ssl and self.udp_crypto:
                    self.log(f"🔒 UDP Server started with AES-256-GCM encryption on {self.host}:{self.port}", "SUCCESS")
                else:
                    self.log(f"UDP Server started on {self.host}:{self.port} (No encryption)", "SUCCESS")
                
                self.log(f"⚠️ Packet Loss Simulation: {self.packet_loss_rate*100:.0f}%", "WARNING")
                threading.Thread(target=self.handle_messages_udp, daemon=True).start()
                threading.Thread(target=self.retransmit_pending_udp, daemon=True).start()
            return True
        except Exception as e:
            self.log(f"Start Server Error: {e}", "ERROR")
            return False

    def stop(self):
        self.running = False
        if self.protocol == 'TCP':
            for c in self.clients[:]:
                try:
                    c.close()
                except:
                    pass
            self.clients = []
            self.nicknames = []
            self.client_map = {}
        else:
            self.clients = {}
            self.client_map = {}
            self.addr_to_nickname = {}
            self.received_msg_ids = {}
        
        self.client_stats = {}
        self.pending_acks = {}
        
        if self.server:
            try:
                self.server.close()
            except:
                pass
            self.server = None
        self.log("Server stopped", "WARNING")
        self.update_clients_list()

    def get_client_stats(self, nickname):
        """Get statistics for a specific client"""
        with self.lock:
            if nickname not in self.client_stats:
                return None
            
            stats = self.client_stats[nickname].copy()
            
            avg_latency = 0.0
            min_latency = 0.0
            max_latency = 0.0
            
            if stats['latency_samples']:
                avg_latency = sum(stats['latency_samples']) / len(stats['latency_samples'])
                min_latency = min(stats['latency_samples'])
                max_latency = max(stats['latency_samples'])
            
            packet_loss_rate = (stats['packet_loss'] / stats['sent_count'] * 100) if stats['sent_count'] > 0 else 0.0
            duplicate_rate = (stats['duplicates'] / stats['received_count'] * 100) if stats['received_count'] > 0 else 0.0
            
            pending_count = 0
            for k, v in self.pending_acks.items():
                if v.get('nickname') == nickname:
                    pending_count += 1
            
            return {
                'sent_count': stats['sent_count'],
                'received_count': stats['received_count'],
                'ack_count': stats['ack_count'],
                'retransmissions': stats['retransmissions'],
                'packet_loss': stats['packet_loss'],
                'packet_loss_rate': packet_loss_rate,
                'duplicates': stats['duplicates'],
                'duplicate_rate': duplicate_rate,
                'avg_latency': avg_latency,
                'min_latency': min_latency,
                'max_latency': max_latency,
                'pending_messages': pending_count,
                'simulated_drops': stats['simulated_drops'],
                'configured_loss_rate': self.packet_loss_rate * 100,
                'ack_timeout': self.ack_timeout,
                'max_retries': self.max_retries,
                'encrypted_messages': stats.get('encrypted_messages', 0),
                'ssl_enabled': (self.use_ssl and self.protocol == 'TCP') or (self.use_ssl and self.udp_crypto and self.protocol == 'UDP')
            }

    def process_queues(self):
        while not self.log_queue.empty():
            try:
                log = self.log_queue.get_nowait()
                st.session_state.server_logs.append(log)
            except queue.Empty:
                break

        while not self.clients_queue.empty():
            try:
                clients_list = self.clients_queue.get_nowait()
                st.session_state.connected_clients = clients_list
            except queue.Empty:
                break
        
        while not self.conversations_queue.empty():
            try:
                conv_update = self.conversations_queue.get_nowait()
                nickname = conv_update['nickname']
                message = conv_update['message']
                
                if 'server_conversations' not in st.session_state:
                    st.session_state.server_conversations = {}
                
                if nickname not in st.session_state.server_conversations:
                    st.session_state.server_conversations[nickname] = []
                
                st.session_state.server_conversations[nickname].append(message)
            except queue.Empty:
                break