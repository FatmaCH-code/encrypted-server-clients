import socket
import threading
import queue
import time
import random
from datetime import datetime
import streamlit as st
import ssl
from udp_crypto import UDPCrypto

class ChatClient:
    def __init__(self, host='127.0.0.1', port=5555, nickname='Guest', PROTO='TCP', use_ssl=True):
        self.host = host
        self.port = port
        self.nickname = nickname
        self.PROTO = PROTO.upper()
        self.use_ssl = use_ssl and (self.PROTO == 'TCP' or self.PROTO == 'UDP')
        self.client = None
        self.connected = False
        self.message_queue = queue.Queue()

        # UDP Encryption
        self.udp_crypto = None
        if self.use_ssl and self.PROTO == 'UDP':
            try:
                self.udp_crypto = UDPCrypto()
            except Exception as e:
                self.use_ssl = False

        # UDP reliability tracking
        self.message_id_counter = 0
        self.pending_messages = {}
        self.received_messages = set()
        self.lock = threading.Lock()
        self.stats = {
            'sent_count': 0,
            'received_count': 0,
            'ack_count': 0,
            'retransmissions': 0,
            'packet_loss': 0,
            'out_of_order': 0,
            'total_latency': 0.0,
            'latency_samples': [],
            'simulated_drops': 0,
            'encrypted_messages': 0
        }

        # UDP Configuration
        self.ack_timeout = 2.0
        self.max_retries = 5
        self.packet_loss_rate = 0.50

        # Create socket
        if self.PROTO == 'TCP':
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def simulate_packet_loss(self):
        """Simule la perte de paquets selon le taux configuré"""
        if self.PROTO == 'UDP':
            return random.random() < self.packet_loss_rate
        return False

    def connect(self):
        try:
            if self.PROTO == 'TCP':
                # Connect to server
                self.client.connect((self.host, self.port))
                
                # Wrap with SSL if enabled
                if self.use_ssl:
                    try:
                        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE  # For self-signed certificates
                        
                        self.client = ssl_context.wrap_socket(self.client, server_hostname=self.host)
                        
                        # Add SSL connection message to queue
                        self.message_queue.put({
                            'time': datetime.now().strftime("%H:%M"),
                            'text': "🔒 Secure SSL connection established!",
                            'system': True,
                            'own': False,
                            'latency': None
                        })
                    except Exception as e:
                        self.message_queue.put({
                            'time': datetime.now().strftime("%H:%M"),
                            'text': f"⚠️ SSL handshake failed: {e}. Connection not secure.",
                            'system': True,
                            'own': False,
                            'latency': None
                        })
                        self.use_ssl = False
                
                self.connected = True
                
                nick_req = self.client.recv(1024).decode('utf-8')
                if nick_req == 'NICK':
                    self.client.send(self.nickname.encode('utf-8'))
                
            else:
                # UDP connection with encryption
                nickname_msg = self.nickname
                
                # Encrypt nickname if UDP encryption is enabled
                if self.use_ssl and self.udp_crypto:
                    try:
                        nickname_msg = self.udp_crypto.encrypt_message(nickname_msg)
                    except:
                        pass
                
                self.client.sendto(nickname_msg.encode('utf-8'), (self.host, self.port))
                self.connected = True
                
                # Add encryption status message
                if self.use_ssl and self.udp_crypto:
                    self.message_queue.put({
                        'time': datetime.now().strftime("%H:%M"),
                        'text': "🔒 UDP connection with AES-256-GCM encryption established!",
                        'system': True,
                        'own': False,
                        'latency': None
                    })
                else:
                    self.message_queue.put({
                        'time': datetime.now().strftime("%H:%M"),
                        'text': "⚠️ UDP mode: No encryption available",
                        'system': True,
                        'own': False,
                        'latency': None
                    })

            threading.Thread(target=self.receive_messages, daemon=True).start()

            if self.PROTO == 'UDP':
                threading.Thread(target=self.retransmit_pending, daemon=True).start()

            return True
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")
            return False

    def receive_messages(self):
        while self.connected:
            try:
                if self.PROTO == 'TCP':
                    self.client.settimeout(1.0)
                    data = self.client.recv(2048)
                    if not data:
                        continue
                    msg = data.decode('utf-8').strip()
                    
                    # Log decryption for encrypted messages
                    if self.use_ssl and msg and not msg.startswith('ACK:'):
                        pass  # Decryption happens automatically
                else:
                    self.client.settimeout(1.0)
                    data, addr = self.client.recvfrom(2048)
                    msg = data.decode('utf-8')
                    
                    # Try to decrypt if encryption is enabled
                    if self.use_ssl and self.udp_crypto and msg.startswith('ENC:'):
                        try:
                            msg = self.udp_crypto.decrypt_message(msg)
                        except Exception as e:
                            continue

                if not msg:
                    continue

                if msg == 'NICK':
                    continue
                    
                elif msg.startswith('ACK:'):
                    if self.simulate_packet_loss():
                        with self.lock:
                            self.stats['simulated_drops'] += 1
                        continue
                    self.handle_ack(msg)
                    
                elif msg.startswith('MSG:'):
                    if self.simulate_packet_loss():
                        with self.lock:
                            self.stats['simulated_drops'] += 1
                        continue
                    self.handle_udp_message(msg, addr if self.PROTO == 'UDP' else None)
                    
                else:
                    receive_time = time.time()
                    timestamp = datetime.now().strftime("%H:%M")
                    latency = None
                    
                    if '|TS:' in msg:
                        parts = msg.split('|TS:')
                        if len(parts) >= 2:
                            try:
                                send_time = float(parts[1].split('|')[0])
                                latency = (receive_time - send_time) * 1000
                                msg = parts[0]
                            except:
                                pass
                    
                    with self.lock:
                        self.stats['received_count'] += 1
                        if self.use_ssl:
                            self.stats['encrypted_messages'] += 1
                        if latency:
                            self.stats['total_latency'] += latency
                            self.stats['latency_samples'].append(latency)
                            if len(self.stats['latency_samples']) > 100:
                                self.stats['latency_samples'] = self.stats['latency_samples'][-100:]
                    
                    is_system = "Connected to" in msg or "disconnected" in msg.lower() or "🔒" in msg or "SSL" in msg or "encryption" in msg.lower()
                    is_own = msg.startswith(self.nickname + ":")
                    
                    self.message_queue.put({
                        'time': timestamp,
                        'text': msg,
                        'own': is_own,
                        'system': is_system,
                        'latency': latency
                    })
                    
            except socket.timeout:
                continue
            except Exception as e:
                if self.connected:
                    self.message_queue.put({
                        'time': datetime.now().strftime("%H:%M"),
                        'text': "Connection lost!",
                        'system': True,
                        'own': False,
                        'latency': None
                    })
                    self.disconnect()
                break

    def handle_ack(self, ack_message):
        try:
            msg_id = int(ack_message.split(':')[1])
            with self.lock:
                if msg_id in self.pending_messages:
                    send_time = self.pending_messages[msg_id]['timestamp']
                    latency = (time.time() - send_time) * 1000
                    self.stats['ack_count'] += 1
                    self.stats['total_latency'] += latency
                    self.stats['latency_samples'].append(latency)
                    if len(self.stats['latency_samples']) > 100:
                        self.stats['latency_samples'] = self.stats['latency_samples'][-100:]
                    
                    # Add the message to UI only after ACK is received (for UDP)
                    if self.PROTO == 'UDP' and 'message_text' in self.pending_messages[msg_id]:
                        timestamp = datetime.now().strftime("%H:%M")
                        self.message_queue.put({
                            'time': timestamp,
                            'text': self.pending_messages[msg_id]['message_text'],
                            'own': True,
                            'system': False,
                            'latency': latency
                        })
                    
                    del self.pending_messages[msg_id]
        except:
            pass

    def handle_udp_message(self, message, addr):
        try:
            parts = message.split(':', 3)
            if len(parts) < 4:
                return
            msg_id = int(parts[1])
            send_time = float(parts[2])
            actual_message = parts[3]
            recv_time = time.time()
            latency = (recv_time - send_time) * 1000

            if self.PROTO == 'UDP' and addr:
                ack_data = f"ACK:{msg_id}"
                
                # Encrypt ACK if encryption enabled
                if self.use_ssl and self.udp_crypto:
                    try:
                        ack_data = self.udp_crypto.encrypt_message(ack_data)
                    except:
                        pass
                
                if not self.simulate_packet_loss():
                    self.client.sendto(ack_data.encode('utf-8'), addr)
                else:
                    with self.lock:
                        self.stats['simulated_drops'] += 1

            with self.lock:
                if msg_id in self.received_messages:
                    return
                self.received_messages.add(msg_id)
                self.stats['received_count'] += 1
                if self.use_ssl and self.udp_crypto:
                    self.stats['encrypted_messages'] += 1
                self.stats['total_latency'] += latency
                self.stats['latency_samples'].append(latency)
                if len(self.stats['latency_samples']) > 100:
                    self.stats['latency_samples'] = self.stats['latency_samples'][-100:]

            is_system = "Connected to" in actual_message or "disconnected" in actual_message.lower() or "encryption" in actual_message.lower()
            is_own = actual_message.startswith(self.nickname + ":")
            
            self.message_queue.put({
                'time': datetime.now().strftime("%H:%M"),
                'text': actual_message,
                'own': is_own,
                'system': is_system,
                'latency': latency
            })
        except:
            pass

    def retransmit_pending(self):
        """Thread de retransmission"""
        while self.connected:
            try:
                time.sleep(0.1)
                current_time = time.time()
                to_retransmit = []
                failed_messages = []

                with self.lock:
                    for msg_id, data in list(self.pending_messages.items()):
                        elapsed = current_time - data['timestamp']
                        if elapsed > self.ack_timeout:
                            if data['retries'] < self.max_retries:
                                to_retransmit.append((msg_id, {
                                    'data': data['data'],
                                    'timestamp': data['timestamp'],
                                    'retries': data['retries']
                                }))
                            else:
                                self.stats['packet_loss'] += 1
                                failed_messages.append(msg_id)

                if failed_messages:
                    with self.lock:
                        for msg_id in failed_messages:
                            if msg_id in self.pending_messages:
                                del self.pending_messages[msg_id]
                    
                    self.message_queue.put({
                        'time': datetime.now().strftime("%H:%M"),
                        'text': f"⚠️ Connection lost: {len(failed_messages)} message(s) failed after {self.max_retries} retries!",
                        'system': True,
                        'own': False,
                        'latency': None
                    })
                    
                    self.connected = False
                    
                    try:
                        disconnect_msg = f"DISCONNECT:{self.nickname}"
                        
                        # Encrypt disconnect message if encryption enabled
                        if self.use_ssl and self.udp_crypto:
                            try:
                                disconnect_msg = self.udp_crypto.encrypt_message(disconnect_msg)
                            except:
                                pass
                        
                        self.client.sendto(disconnect_msg.encode('utf-8'), (self.host, self.port))
                    except:
                        pass
                    
                    try:
                        self.client.close()
                    except:
                        pass
                    
                    break

                for msg_id, data in to_retransmit:
                    try:
                        if not self.connected:
                            break
                            
                        if not self.simulate_packet_loss():
                            self.client.sendto(data['data'], (self.host, self.port))
                        else:
                            with self.lock:
                                self.stats['simulated_drops'] += 1
                        
                        with self.lock:
                            if msg_id in self.pending_messages:
                                self.pending_messages[msg_id]['timestamp'] = time.time()
                                self.pending_messages[msg_id]['retries'] += 1
                                self.stats['retransmissions'] += 1
                    except Exception as e:
                        self.connected = False
                        break

            except Exception as e:
                break

    def send_message(self, message):
        if not self.connected:
            return False
            
        try:
            full_message = f"{self.nickname}: {message}"
            send_time = time.time()

            if self.PROTO == 'UDP':
                with self.lock:
                    msg_id = self.message_id_counter
                    self.message_id_counter += 1
                    self.stats['sent_count'] += 1
                    if self.use_ssl and self.udp_crypto:
                        self.stats['encrypted_messages'] += 1

                udp_msg = f"MSG:{msg_id}:{send_time}:{full_message}"
                
                # Encrypt message if UDP encryption is enabled
                if self.use_ssl and self.udp_crypto:
                    try:
                        udp_msg = self.udp_crypto.encrypt_message(udp_msg)
                    except:
                        pass
                
                data = udp_msg.encode('utf-8')
                
                if not self.simulate_packet_loss():
                    self.client.sendto(data, (self.host, self.port))
                else:
                    with self.lock:
                        self.stats['simulated_drops'] += 1
                
                # Store message text in pending_messages to display after ACK
                with self.lock:
                    self.pending_messages[msg_id] = {
                        'data': data, 
                        'timestamp': send_time, 
                        'retries': 0,
                        'message_text': full_message  # Store the message text
                    }
            else:
                # TCP: send immediately and add to UI
                tcp_msg = f"{full_message}|TS:{send_time}|"
                self.client.send(tcp_msg.encode('utf-8'))
                with self.lock:
                    self.stats['sent_count'] += 1
                    if self.use_ssl:
                        self.stats['encrypted_messages'] += 1

            return True
        except:
            self.disconnect()
            return False

    def disconnect(self):
        self.connected = False
        if self.client:
            try:
                self.client.close()
            except:
                pass

    def process_queue(self):
        while not self.message_queue.empty():
            try:
                msg = self.message_queue.get_nowait()
                if 'messages' not in st.session_state:
                    st.session_state.messages = []
                st.session_state.messages.append(msg)
            except queue.Empty:
                break

    def get_stats(self):
        with self.lock:
            avg_latency = 0.0
            if self.stats['latency_samples']:
                avg_latency = sum(self.stats['latency_samples']) / len(self.stats['latency_samples'])
            packet_loss_rate = (self.stats['packet_loss'] / self.stats['sent_count'] * 100) if self.stats['sent_count'] else 0.0
            out_of_order_rate = (self.stats['out_of_order'] / self.stats['received_count'] * 100) if self.stats['received_count'] else 0.0

            return {
                'sent_count': self.stats['sent_count'],
                'received_count': self.stats['received_count'],
                'ack_count': self.stats['ack_count'],
                'retransmissions': self.stats['retransmissions'],
                'packet_loss': self.stats['packet_loss'],
                'packet_loss_rate': packet_loss_rate,
                'out_of_order': self.stats['out_of_order'],
                'out_of_order_rate': out_of_order_rate,
                'avg_latency': avg_latency,
                'min_latency': min(self.stats['latency_samples']) if self.stats['latency_samples'] else 0.0,
                'max_latency': max(self.stats['latency_samples']) if self.stats['latency_samples'] else 0.0,
                'simulated_drops': self.stats['simulated_drops'],
                'configured_loss_rate': self.packet_loss_rate * 100,
                'ack_timeout': self.ack_timeout,
                'max_retries': self.max_retries,
                'encrypted_messages': self.stats['encrypted_messages'],
                'ssl_enabled': self.use_ssl
            }