# 123456789_Client.py - Client side for Hospital Appointment System

import socket
import threading
import sys

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 1024

class Client:
    def __init__(self, client_type, connection_type):
        self.client_type = client_type
        self.connection_type = connection_type
        self.socket = None
        self.name = None
        self.running = True

        if client_type not in ["Doktor", "Hasta"] or connection_type not in ["TCP", "UDP"]:
            print("Kullanım hatası: İstemci tipi veya bağlantı tipi hatalı.")
            sys.exit(1)

        if client_type == "Doktor" and connection_type != "TCP":
            print("Hatalı kullanım: Doktor sadece TCP kullanabilir.")
            sys.exit(1)

        self.initialize_socket()

    def initialize_socket(self):
        if self.connection_type == "TCP":
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.socket.connect((HOST, PORT))
                self.socket.send(f"{self.client_type},{self.connection_type}".encode())
            except Exception as e:
                print(f"Bağlantı hatası: {e}")
                sys.exit(1)
        else:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.sendto(f"{self.client_type},{self.connection_type}".encode(), (HOST, PORT))

    def start(self):
        receive_thread = threading.Thread(target=self.receive_messages)
        receive_thread.daemon = True
        receive_thread.start()

        try:
            while self.running:
                if self.client_type == "Doktor":
                    self.doctor_interface()
                else:
                    self.patient_interface()
        except KeyboardInterrupt:
            print("İstemci kapatılıyor...")
        finally:
            if self.socket:
                self.socket.close()

    def receive_messages(self):
        try:
            while self.running:
                if self.connection_type == "TCP":
                    data = self.socket.recv(BUFFER_SIZE)
                    if not data:
                        print("Sunucu bağlantısı kesildi.")
                        self.running = False
                        break
                    message = data.decode()
                else:
                    data, _ = self.socket.recvfrom(BUFFER_SIZE)
                    message = data.decode()

                self.process_message(message)
        except Exception as e:
            if self.running:
                print(f"Mesaj alma hatası: {e}")
                self.running = False

    def process_message(self, message):
        print(f"\n[SERVER]: {message}")

        if message.startswith("Hoşgeldiniz"):
            parts = message.split()
            if len(parts) > 1:
                self.name = parts[1]
                print(f"İstemci adınız: {self.name}")

        if "->" in message and self.client_type == "Hasta":
            print("Bir doktor sizi çağırdı. Kabul etmek için 'accept' yazınız.")

        if any(x in message.lower() for x in ["geçmiş olsun", "kapanıyor", "bağlantı kesildi"]):
            print("Bağlantı kapatılıyor.")
            self.running = False

    def doctor_interface(self):
        command = input("\nDoktor Komutları ('call' hasta çağır | 'exit' çıkış): ")
        if command.lower() == "call":
            self.socket.send("Hasta Kabul".encode())
        elif command.lower() == "exit":
            self.running = False

    def patient_interface(self):
        command = input("\nHasta Komutları ('accept' randevuyu kabul et | 'exit' çıkış): ")
        if command.lower() == "accept":
            msg = f"ACCEPT:{self.name}" if self.name else "ACCEPT"
            if self.connection_type == "TCP":
                self.socket.send(msg.encode())
            else:
                self.socket.sendto(msg.encode(), (HOST, PORT))
        elif command.lower() == "exit":
            self.running = False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Kullanım: python 123456789_Client.py <Doktor/Hasta> <TCP/UDP>")
        sys.exit(1)

    tip = sys.argv[1]
    baglanti = sys.argv[2]

    client = Client(tip, baglanti)
    client.start()
