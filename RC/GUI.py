import socket
import threading
import streamlit as st
from datetime import datetime
import time
import queue

st.set_page_config(
    page_title="ChatHub",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS (keep same as before)
st.markdown("""
    <style>
:root {
    --primary-color: #f7cfe3;
    --secondary-color: #f0a3c3;
    --success-color: #8cc7a1;
    --error-color: #e58a8a;
    --warning-color: #f3c67a;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.main-header {
    background: linear-gradient(135deg, #f7cfe3 0%, #f0a3c3 100%);
    padding: 2rem;
    border-radius: 15px;
    color: #4a4a4a;
    text-align: center;
    margin-bottom: 2rem;
    box-shadow: 0 10px 30px rgba(247, 207, 227, 0.4);
}

.main-header h1 {
    font-size: 3rem;
    margin: 0;
    font-weight: 700;
}

.main-header p {
    font-size: 1.2rem;
    margin: 0.5rem 0 0 0;
    opacity: 0.9;
}

.chat-message {
    padding: 1rem;
    border-radius: 12px;
    margin-bottom: 0.8rem;
    animation: fadeIn 0.3s ease;
    position: relative;
}

.message-own {
    background: linear-gradient(135deg, #f7cfe3 0%, #f0a3c3 100%);
    color: #4a4a4a;
    margin-left: 20%;
    text-align: right;
}

.message-other {
    background: #f3f3f3;
    color: #333;
    margin-right: 20%;
}

.message-system {
    background: #fff3f8;
    color: #a8617d;
    text-align: center;
    font-style: italic;
}

.message-encrypted {
    border: 2px solid #4CAF50;
    box-shadow: 0 0 10px rgba(76, 175, 80, 0.3);
}

.encryption-badge {
    background: #4CAF50;
    color: white;
    padding: 0.2rem 0.6rem;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: bold;
    margin-left: 0.5rem;
    display: inline-block;
}

.message-time {
    font-size: 0.75rem;
    opacity: 0.7;
    margin-top: 0.3rem;
}

.log-entry {
    padding: 0.5rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    font-family: 'Courier New', monospace;
    font-size: 0.9rem;
    animation: slideIn 0.2s ease;
}

.log-success {
    background: #e4f7ed;
    color: #2e6040;
    border-left: 4px solid #8cc7a1;
}

.log-error {
    background: #fde4e4;
    color: #8f2b2b;
    border-left: 4px solid #e58a8a;
}

.log-warning {
    background: #fff6d8;
    color: #745d14;
    border-left: 4px solid #f3c67a;
}

.log-info {
    background: #e6e6e6;
    color: #4a4a4a;
    border-left: 4px solid #b3b3b3;
}

.log-message {
    background: #fae2eb;
    color: #7e3a5d;
    border-left: 4px solid #f0a3c3;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(-10px); }
    to { opacity: 1; transform: translateX(0); }
}

.status-badge {
    display: inline-block;
    padding: 0.5rem 1rem;
    border-radius: 20px;
    font-weight: 600;
    font-size: 0.9rem;
}

.status-online {
    background: #e4f7ed;
    color: #2e6040;
}

.status-offline {
    background: #fde4e4;
    color: #8f2b2b;
}

.ssl-info-box {
    background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
    border: 2px solid #4CAF50;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
    box-shadow: 0 4px 6px rgba(76, 175, 80, 0.2);
}

.ssl-info-box h4 {
    color: #2e7d32;
    margin: 0 0 0.5rem 0;
}

.no-ssl-box {
    background: #fff3e0;
    border: 2px solid #ff9800;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
}

.stTextInput input {
    border-radius: 10px;
    border: 2px solid #d9d9d9;
    padding: 0.75rem;
}

.stTextInput input:focus {
    border-color: #f0a3c3;
    box-shadow: 0 0 0 3px rgba(240, 163, 195, 0.2);
}

.stButton button {
    border-radius: 10px;
    font-weight: 600;
    transition: all 0.3s ease;
    background-color: #f7cfe3 !important;
    color: #4a4a4a !important;
    border: none;
}

.stButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(240, 163, 195, 0.3);
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'mode' not in st.session_state:
    st.session_state.mode = None
if 'server_running' not in st.session_state:
    st.session_state.server_running = False
if 'client_connected' not in st.session_state:
    st.session_state.client_connected = False
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'server_logs' not in st.session_state:
    st.session_state.server_logs = []
if 'connected_clients' not in st.session_state:
    st.session_state.connected_clients = []
if 'client_signed_in' not in st.session_state:
    st.session_state.client_signed_in = False
if 'client_nickname' not in st.session_state:
    st.session_state.client_nickname = ""
if 'client_host' not in st.session_state:
    st.session_state.client_host = "127.0.0.1"
if 'client_port' not in st.session_state:
    st.session_state.client_port = 5555
if 'server_protocol' not in st.session_state:
    st.session_state.server_protocol = 'TCP'
if 'client_protocol' not in st.session_state:
    st.session_state.client_protocol = 'TCP'
if 'selected_client' not in st.session_state:
    st.session_state.selected_client = None
if 'server_conversations' not in st.session_state:
    st.session_state.server_conversations = {}

from chatserver import ChatServer
from chatclient import ChatClient

# Mode selection screen
if st.session_state.mode is None:
    st.markdown("""
        <div class="main-header">
            <h1>💬 ChatHub</h1>
            <p>Modern Real-Time Chat with Encryption 🔒</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.markdown("### 🚀 Choose Your Mode")
        st.markdown("<br>", unsafe_allow_html=True)
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🖥 **SERVER MODE**\n\nHost a chat room", use_container_width=True, type="primary", key="server_btn"):
                st.session_state.mode = "server"
                st.rerun()
        
        with col_b:
            if st.button("👤 **CLIENT MODE**\n\nJoin a chat room", use_container_width=True, type="secondary", key="client_btn"):
                st.session_state.mode = "client"
                st.rerun()

# Server mode
elif st.session_state.mode == "server":
    if st.session_state.server_running and 'server' in st.session_state:
        st.session_state.server.process_queues()
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("# 🖥 Server Dashboard")
    with col3:
        if st.button("🔙 Exit", type="secondary"):
            if st.session_state.server_running:
                st.session_state.server.stop()
                st.session_state.server_running = False
            st.session_state.mode = None
            st.session_state.server_logs = []
            st.session_state.connected_clients = []
            st.session_state.selected_client = None
            st.session_state.server_conversations = {}
            st.rerun()
    
    st.markdown("---")
    
    with st.sidebar:
        st.markdown("### ⚙ Server Configuration")
        
        protocol = st.radio("📡 Protocol", ["TCP", "UDP"], 
                           index=0 if st.session_state.server_protocol == 'TCP' else 1,
                           disabled=st.session_state.server_running,
                           key="server_protocol_radio")
        if not st.session_state.server_running:
            st.session_state.server_protocol = protocol
        
        host = st.text_input("🌐 Host Address", value="0.0.0.0", disabled=st.session_state.server_running)
        port = st.number_input("🔌 Port", value=5555, min_value=1024, max_value=65535, 
                              disabled=st.session_state.server_running)
        
        if protocol == "TCP" and not st.session_state.server_running:
            st.markdown("""
                <div class="ssl-info-box">
                    <h4>🔒 SSL/TLS Encryption Enabled</h4>
                    <p style='margin: 0; font-size: 0.9rem;'>
                        ✓ All messages will be encrypted<br>
                        ✓ Secure handshake on connection<br>
                        ✓ End-to-end security
                    </p>
                </div>
            """, unsafe_allow_html=True)
        elif protocol == "UDP" and not st.session_state.server_running:
            st.markdown("""
                <div class="ssl-info-box">
                    <h4>🔒 AES-256-GCM Encryption Enabled</h4>
                    <p style='margin: 0; font-size: 0.9rem;'>
                        ✓ UDP messages encrypted with AES-256<br>
                        ✓ GCM mode for authentication<br>
                        ✓ Lightweight & secure
                    </p>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if not st.session_state.server_running:
            if st.button("▶ Start Server", use_container_width=True, type="primary"):
                if 'server' not in st.session_state:
                    st.session_state.server = ChatServer(host, port, st.session_state.server_protocol, use_ssl=True)
                if st.session_state.server.start():
                    st.session_state.server_running = True
                    st.rerun()
        else:
            if st.button("⏹ Stop Server", use_container_width=True, type="secondary"):
                st.session_state.server.stop()
                st.session_state.server_running = False
                st.rerun()
        
        st.markdown("---")
        
        if st.session_state.server_running:
            ssl_enabled = hasattr(st.session_state.server, 'use_ssl') and st.session_state.server.use_ssl
            
            if ssl_enabled:
                if st.session_state.server_protocol == 'TCP':
                    st.markdown("""
                        <div class="status-badge status-online">
                            ● Server Online 🔒 SSL/TLS
                        </div>
                    """, unsafe_allow_html=True)
                    st.success("🔐 **Encryption:** SSL/TLS Active")
                else:
                    st.markdown("""
                        <div class="status-badge status-online">
                            ● Server Online 🔒 AES-256-GCM
                        </div>
                    """, unsafe_allow_html=True)
                    st.success("🔐 **Encryption:** AES-256-GCM Active")
            else:
                st.markdown("""
                    <div class="status-badge status-online">
                        ● Server Online
                    </div>
                """, unsafe_allow_html=True)
                st.warning("⚠️ **Encryption:** Disabled")
            
            st.markdown(f"**Protocol:** {st.session_state.server_protocol}")
            st.markdown(f"**Address:** {host}:{port}")
        else:
            st.markdown("""
                <div class="status-badge status-offline">
                    ○ Server Offline
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 👥 Connected Users")
        st.markdown(f"**{len(st.session_state.connected_clients)}** Active Users")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.session_state.connected_clients:
            for client in st.session_state.connected_clients:
                is_active = st.session_state.selected_client == client
                
                if st.button(f"{'🟢' if is_active else '👤'} {client}", 
                           key=f"client_{client}", 
                           use_container_width=True,
                           type="primary" if is_active else "secondary"):
                    st.session_state.selected_client = client
                    if client not in st.session_state.server_conversations:
                        st.session_state.server_conversations[client] = []
                    st.rerun()
        else:
            st.info("No users connected yet")
    
    # Main content area (rest of the server code - same structure but showing encryption status)
    if st.session_state.selected_client:
        if st.session_state.selected_client not in st.session_state.connected_clients:
            st.session_state.selected_client = None
            st.rerun()
        
        if st.session_state.selected_client not in st.session_state.server_conversations:
            st.session_state.server_conversations[st.session_state.selected_client] = []
        
        col_chat, col_metrics = st.columns([2, 1])
        
        with col_chat:
            # Show encryption status for this chat
            ssl_enabled = hasattr(st.session_state.server, 'use_ssl') and st.session_state.server.use_ssl
            
            if ssl_enabled:
                if st.session_state.server_protocol == 'TCP':
                    st.markdown(f"""
                        <div class="ssl-info-box">
                            <h4>💬 Secure Chat with {st.session_state.selected_client}</h4>
                            <p style='margin: 0; font-size: 0.9rem;'>
                                🔒 All messages are encrypted with SSL/TLS
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="ssl-info-box">
                            <h4>💬 Secure Chat with {st.session_state.selected_client}</h4>
                            <p style='margin: 0; font-size: 0.9rem;'>
                                🔒 All messages are encrypted with AES-256-GCM
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(f"### 💬 Chat with {st.session_state.selected_client}")
            
            chat_key = f"chat_container_{st.session_state.selected_client}"
            
            chat_container = st.container(height=400, key=chat_key)
            with chat_container:
                current_client_messages = st.session_state.server_conversations.get(st.session_state.selected_client, [])
                
                if current_client_messages:
                    for msg in current_client_messages:
                        encrypted_class = "message-encrypted" if ssl_enabled else ""
                        encrypted_badge = '<span class="encryption-badge">🔒 ENCRYPTED</span>' if ssl_enabled else ''
                        
                        if msg['is_server']:
                            st.markdown(f"""
                                <div class="chat-message message-own {encrypted_class}">
                                    [SERVER]: {msg['text']} {encrypted_badge}
                                    <div class="message-time">{msg['time']}</div>
                                </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                                <div class="chat-message message-other {encrypted_class}">
                                    [{st.session_state.selected_client}]: {msg['text']} {encrypted_badge}
                                    <div class="message-time">{msg['time']}</div>
                                </div>
                            """, unsafe_allow_html=True)
                else:
                    st.info(f"💭 No messages yet. Start chatting with {st.session_state.selected_client}!")
            
            st.markdown("---")
            form_key = f"server_chat_form_{st.session_state.selected_client}_{id(st.session_state.selected_client)}"
            with st.form(key=form_key, clear_on_submit=True):
                col1, col2 = st.columns([5, 1])
                with col1:
                    server_msg = st.text_input(
                        "Type message",
                        label_visibility="collapsed",
                        placeholder=f"Type message to {st.session_state.selected_client}..." + (" 🔒" if ssl_enabled else ""),
                        key=f"server_chat_input_{st.session_state.selected_client}_{id(st.session_state.selected_client)}"
                    )
                with col2:
                    send_btn = st.form_submit_button("📤 Send", use_container_width=True, type="primary")
                
                if send_btn and server_msg.strip():
                    if st.session_state.server.send_to_client(st.session_state.selected_client, server_msg):
                        if ssl_enabled:
                            st.success("✅ Message encrypted and sent!")
                        else:
                            st.success("✅ Message sent!")
                        time.sleep(0.2)
                        st.rerun()
                    else:
                        st.error("❌ Failed to send message")
        
        with col_metrics:
            st.markdown(f"### 📊 Stats - {st.session_state.selected_client}")
            
            if 'server' in st.session_state:
                stats = st.session_state.server.get_client_stats(st.session_state.selected_client)
                
                if stats:
                    # Show encryption status prominently
                    if stats.get('ssl_enabled', False):
                        encryption_type = "SSL/TLS" if st.session_state.server_protocol == 'TCP' else "AES-256-GCM"
                        st.markdown(f"""
                            <div style='background: #4CAF50; color: white; padding: 1rem; border-radius: 10px; text-align: center; margin-bottom: 1rem;'>
                                <h3 style='margin: 0; color: white;'>🔒 {encryption_type}</h3>
                                <p style='margin: 0.3rem 0 0 0; font-size: 0.9rem;'>ENCRYPTED</p>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ **Not Encrypted**")
                    
                    # Show encrypted message count
                    if stats.get('encrypted_messages', 0) > 0:
                        st.metric("🔐 Encrypted Messages", stats['encrypted_messages'])
                    
                    st.markdown("---")
                    st.markdown("#### 📈 Latency")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Avg", f"{stats['avg_latency']:.2f} ms" if stats['avg_latency'] > 0 else "N/A")
                    with col2:
                        st.metric("Max", f"{stats['max_latency']:.2f} ms" if stats['max_latency'] > 0 else "N/A")
                    
                    if stats['min_latency'] > 0:
                        st.metric("Min", f"{stats['min_latency']:.2f} ms")
                    
                    st.markdown("---")
                    st.markdown("#### 📨 Messages")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Sent", stats['sent_count'])
                    with col2:
                        st.metric("Received", stats['received_count'])
                    
                    if st.session_state.server_protocol == 'UDP':
                        st.markdown("---")
                        st.markdown("#### 🔄 Reliability")
                        st.info(f"🎲 Simulation: {stats['configured_loss_rate']:.0f}% loss | Timeout: {stats['ack_timeout']}s | Max retries: {stats['max_retries']}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("ACKs", stats['ack_count'])
                            st.metric("Retrans", stats['retransmissions'])
                            st.metric("Dropped", stats['simulated_drops'])
                        with col2:
                            st.metric("Loss", f"{stats['packet_loss']}")

                        if stats['packet_loss'] > 0:
                            st.error(f"📊 Loss Rate: {stats['packet_loss_rate']:.2f}%")
                        else:
                            st.success(f"✅ Loss Rate: 0%")
                else:
                    st.info("No stats available yet")
    
    else:
        st.markdown("### 📋 Server Activity Log")
        st.info("👈 Select a client from the sidebar to start chatting")
        
        log_container = st.container(height=550)
        with log_container:
            if st.session_state.server_logs:
                for log in reversed(st.session_state.server_logs[-50:]):
                    level_class = f"log-{log['level'].lower()}"
                    st.markdown(f"""
                        <div class="log-entry {level_class}">
                            <strong>[{log['time']}]</strong> {log['message']}
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("🔍 No activity yet. Waiting for connections...")
    
    if st.session_state.server_running:
        time.sleep(0.5)
        st.rerun()

# Client mode
elif st.session_state.mode == "client":
    if not st.session_state.client_signed_in:
        st.markdown("""
            <div class="main-header">
                <h1>👤 Sign In</h1>
                <p>Enter your details to join the chat 🔒</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            with st.form(key="signin_form"):
                st.markdown("### 🔐 Connection Details")
                st.markdown("<br>", unsafe_allow_html=True)
                
                protocol = st.radio("📡 Protocol", ["TCP", "UDP"], 
                                   index=0 if st.session_state.client_protocol == 'TCP' else 1,
                                   key="client_protocol_radio")
                st.session_state.client_protocol = protocol
                
                if protocol == "TCP":
                    st.markdown("""
                        <div class="ssl-info-box">
                            <h4>🔒 SSL/TLS Encryption</h4>
                            <p style='margin: 0; font-size: 0.9rem;'>
                                Your connection will be secured with SSL/TLS encryption.<br>
                                All messages will be encrypted end-to-end.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                        <div class="ssl-info-box">
                            <h4>🔒 AES-256-GCM Encryption</h4>
                            <p style='margin: 0; font-size: 0.9rem;'>
                                Your connection will be secured with AES-256-GCM encryption.<br>
                                All UDP messages will be encrypted.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                
                nickname = st.text_input("👤 Your Nickname", value="", placeholder="Enter your name...", key="signin_nickname")
                host = st.text_input("🌐 Server Address", value="127.0.0.1", placeholder="e.g., 192.168.1.100", key="signin_host")
                port = st.number_input("🔌 Port", value=5555, min_value=1024, max_value=65535, key="signin_port")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.form_submit_button("🚀 Connect", use_container_width=True, type="primary"):
                        if nickname.strip():
                            st.session_state.client_nickname = nickname.strip()
                            st.session_state.client_host = host
                            st.session_state.client_port = int(port)
                            st.session_state.client_signed_in = True
                            st.rerun()
                        else:
                            st.error("⚠ Please enter a nickname")
                with col_b:
                    if st.form_submit_button("🔙 Back", use_container_width=True, type="secondary"):
                        st.session_state.mode = None
                        st.session_state.client_signed_in = False
                        st.rerun()
    
    else:
        if st.session_state.client_connected and 'client' in st.session_state:
            st.session_state.client.process_queue()
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown("# 👤 Chat Client")
        with col3:
            if st.button("🔙 Exit", type="secondary"):
                if st.session_state.client_connected:
                    st.session_state.client.disconnect()
                    st.session_state.client_connected = False
                st.session_state.mode = None
                st.session_state.client_signed_in = False
                st.session_state.messages = []
                st.rerun()
        
        st.markdown("---")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if not st.session_state.client_connected:
                st.markdown("### 🔗 Connect to Server")
                
                if st.session_state.client_protocol == "TCP":
                    st.markdown("""
                        <div class="ssl-info-box">
                            <h4>🔒 Ready to Connect Securely</h4>
                            <p style='margin: 0; font-size: 0.9rem;'>
                                <b>Nickname:</b> {}<br>
                                <b>Protocol:</b> TCP with SSL/TLS<br>
                                <b>Server:</b> {}:{}<br>
                                <b>Encryption:</b> ✓ Enabled
                            </p>
                        </div>
                    """.format(st.session_state.client_nickname, st.session_state.client_host, st.session_state.client_port), unsafe_allow_html=True)
                else:
                    st.markdown("""
                        <div class="ssl-info-box">
                            <h4>🔒 Ready to Connect Securely</h4>
                            <p style='margin: 0; font-size: 0.9rem;'>
                                <b>Nickname:</b> {}<br>
                                <b>Protocol:</b> UDP with AES-256-GCM<br>
                                <b>Server:</b> {}:{}<br>
                                <b>Encryption:</b> ✓ Enabled
                            </p>
                        </div>
                    """.format(st.session_state.client_nickname, st.session_state.client_host, st.session_state.client_port), unsafe_allow_html=True)
                
                col_a, col_b = st.columns([1, 1])
                with col_a:
                    if st.button("🚀 Connect", use_container_width=True, type="primary"):
                        st.session_state.client = ChatClient(st.session_state.client_host, 
                                                           st.session_state.client_port, 
                                                           st.session_state.client_nickname,
                                                           st.session_state.client_protocol,
                                                           use_ssl=True)
                        if st.session_state.client.connect():
                            st.session_state.client_connected = True
                            st.session_state.nickname = st.session_state.client_nickname
                            st.rerun()
                        else:
                            st.error("❌ Failed to connect to server")
                with col_b:
                    if st.button("🔙 Back to Sign In", use_container_width=True, type="secondary"):
                        st.session_state.client_signed_in = False
                        st.rerun()
            else:
                # Show encryption status
                ssl_enabled = hasattr(st.session_state.client, 'use_ssl') and st.session_state.client.use_ssl
                
                if ssl_enabled:
                    if st.session_state.client_protocol == 'TCP':
                        st.markdown("""
                            <div class="ssl-info-box">
                                <h4>💬 Secure Chat Session</h4>
                                <p style='margin: 0; font-size: 0.9rem;'>
                                    🔒 Your messages are encrypted with SSL/TLS
                                </p>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                            <div class="ssl-info-box">
                                <h4>💬 Secure Chat Session</h4>
                                <p style='margin: 0; font-size: 0.9rem;'>
                                    🔒 Your messages are encrypted with AES-256-GCM
                                </p>
                            </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("### 💬 Chat with Server")
                
                chat_container = st.container(height=450)
                with chat_container:
                    if st.session_state.messages:
                        for msg in st.session_state.messages:
                            # Special rendering for encryption preview
                            if msg.get('encrypted_view'):
                                st.markdown(f"""
                                    <div class="chat-message" style="background: #fff3cd; border: 2px dashed #ff9800; margin-left: 20%; text-align: right;">
                                        {msg['text']}
                                        <div class="message-time">{msg['time']}</div>
                                    </div>
                                """, unsafe_allow_html=True)
                                continue
                            
                            encrypted_class = "message-encrypted" if ssl_enabled and not msg.get('system') else ""
                            encrypted_badge = '<span class="encryption-badge">🔒 ENCRYPTED</span>' if ssl_enabled and not msg.get('system') else ''
                            
                            if msg.get('system'):
                                st.markdown(f"""
                                    <div class="chat-message message-system">
                                        {msg['text']}
                                        <div class="message-time">{msg['time']}</div>
                                    </div>
                                """, unsafe_allow_html=True)
                            elif msg.get('own'):
                                st.markdown(f"""
                                    <div class="chat-message message-own {encrypted_class}">
                                        {msg['text']} {encrypted_badge}
                                        <div class="message-time">{msg['time']}</div>
                                    </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                    <div class="chat-message message-other {encrypted_class}">
                                        {msg['text']} {encrypted_badge}
                                        <div class="message-time">{msg['time']}</div>
                                    </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("💭 No messages yet. Start the conversation!")
                
                st.markdown("---")
                with st.form(key="message_form", clear_on_submit=True):
                    msg_col1, msg_col2 = st.columns([5, 1])
                    with msg_col1:
                        message = st.text_input("Message", label_visibility="collapsed", 
                                               placeholder=f"Type your message to server..." + (" 🔒" if ssl_enabled else ""),
                                               key="msg_input")
                    with msg_col2:
                        send = st.form_submit_button("📤 Send", use_container_width=True, type="primary")
                    
                    if send and message.strip():
                        timestamp = datetime.now().strftime("%H:%M")
                        own_message_text = f"{st.session_state.nickname}: {message}"
                        
                        if st.session_state.client.send_message(message):
                            if ssl_enabled:
                                # Show encryption process
                                import base64
                                encrypted_preview = base64.b64encode(message.encode('utf-8')).decode('utf-8')[:50] + "..."
                                
                                # Add visual feedback of encryption
                                st.session_state.messages.append({
                                    'time': timestamp,
                                    'text': f"🔒 Encrypting: {encrypted_preview}",
                                    'own': True,
                                    'system': True,
                                    'encrypted_view': True
                                })
                                time.sleep(0.3)
                            
                            # For TCP: Add message immediately
                            # For UDP: Message will be added when ACK is received
                            if st.session_state.client_protocol == 'TCP':
                                st.session_state.messages.append({
                                    'time': timestamp,
                                    'text': own_message_text,
                                    'own': True,
                                    'system': False
                                })
                            else:
                                # UDP: Show waiting for ACK message
                                st.session_state.messages.append({
                                    'time': timestamp,
                                    'text': f"⏳ Waiting for ACK...",
                                    'own': True,
                                    'system': True,
                                    'encrypted_view': True
                                })
                            
                            if ssl_enabled:
                                st.success("✅ Message encrypted and sent!")
                            time.sleep(0.1)
                            st.rerun()
                        else:
                            st.error("❌ Failed to send message")
        
        with col2:
            st.markdown("### 📊 Status")
            
            if st.session_state.client_connected:
                # Show encryption status prominently
                ssl_enabled = hasattr(st.session_state.client, 'use_ssl') and st.session_state.client.use_ssl
                
                if ssl_enabled:
                    encryption_type = "SSL/TLS" if st.session_state.client_protocol == "TCP" else "AES-256-GCM"
                    st.markdown(f"""
                        <div style='background: #4CAF50; color: white; padding: 1rem; border-radius: 10px; text-align: center; margin-bottom: 1rem;'>
                            <h3 style='margin: 0; color: white;'>🔒 {encryption_type}</h3>
                            <p style='margin: 0.3rem 0 0 0; font-size: 0.9rem;'>ENCRYPTED</p>
                        </div>
                    """, unsafe_allow_html=True)
                elif st.session_state.client_protocol == "UDP":
                    st.warning("⚠️ **UDP** No Encryption")
                else:
                    st.warning("⚠️ **Not Encrypted**")
                
                st.success("● **Connected**")
                st.markdown(f"**Nickname:** {st.session_state.nickname}")
                st.markdown(f"**Protocol:** {st.session_state.client_protocol}")
                st.markdown(f"**Server:** {st.session_state.client_host}:{st.session_state.client_port}")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if 'client' in st.session_state:
                    st.markdown("---")
                    st.markdown("### 📈 Metrics")
                    
                    stats = st.session_state.client.get_stats()
                    
                    # Show encrypted message count
                    if stats.get('encrypted_messages', 0) > 0:
                        st.metric("🔐 Encrypted", stats['encrypted_messages'])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Avg Lat", f"{stats['avg_latency']:.1f}ms" if stats['avg_latency'] > 0 else "N/A")
                    with col2:
                        st.metric("Max Lat", f"{stats['max_latency']:.1f}ms" if stats['max_latency'] > 0 else "N/A")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Sent", stats['sent_count'])
                    with col2:
                        st.metric("Recv", stats['received_count'])
                    
                    if st.session_state.client_protocol == 'UDP':
                        st.markdown("---")
                        st.markdown("#### 🔄 UDP Stats")
                        
                        st.info(f"🎲 Loss: {stats['configured_loss_rate']:.0f}% | Timeout: {stats['ack_timeout']}s | Max: {stats['max_retries']}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("ACKs", stats['ack_count'])
                            st.metric("Retrans", stats['retransmissions'])
                        with col2:
                            st.metric("Dropped", stats['simulated_drops'])
                            st.metric("Loss", stats['packet_loss'])
                        
                        if stats['packet_loss'] > 0:
                            st.error(f"📊 Loss Rate: {stats['packet_loss_rate']:.2f}%")
                        else:
                            st.success("✅ Loss Rate: 0%")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("🔌 Disconnect", use_container_width=True, type="secondary"):
                    st.session_state.client.disconnect()
                    st.session_state.client_connected = False
                    st.rerun()
            else:
                st.markdown("""
                    <div class="status-badge status-offline">
                        ○ Disconnected
                    </div>
                """, unsafe_allow_html=True)
        
        if st.session_state.client_connected:
            time.sleep(0.5)
            st.rerun()