# 123456789_Server.py - Server side for Hospital Appointment System

import socket
import threading
import select
import time
import sys
import queue

HOST = '127.0.0.1'
PORT = 12345
BUFFER_SIZE = 1024

doctors = {}
patients = {}
waiting_patients = queue.Queue()
client_counter = 0
lock = threading.Lock()

class Server:
    def __init__(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind((HOST, PORT))
        self.tcp_socket.listen(5)

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind((HOST, PORT))

        print(f"[SERVER] {HOST}:{PORT} dinleniyor...")

    def start(self):
        threading.Thread(target=self.handle_udp_connections, daemon=True).start()
        while True:
            client_socket, addr = self.tcp_socket.accept()
            threading.Thread(target=self.handle_tcp_client, args=(client_socket, addr), daemon=True).start()

    def handle_tcp_client(self, client_socket, addr):
        try:
            data = client_socket.recv(BUFFER_SIZE).decode()
            client_type, conn_type = data.split(',')
            if client_type == "Doktor":
                self.register_doctor(client_socket, addr)
            elif client_type == "Hasta":
                self.register_patient(client_socket, addr, True)
        except Exception as e:
            print(f"[HATA] TCP istemci: {e}")
            client_socket.close()

    def handle_udp_connections(self):
        while True:
            try:
                data, addr = self.udp_socket.recvfrom(BUFFER_SIZE)
                msg = data.decode()
                if msg.startswith("Hasta"):
                    self.register_patient(self.udp_socket, addr, False)
                elif msg.startswith("ACCEPT"):
                    name = msg.split(':')[1]
                    self.patient_accept_appointment(name)
            except Exception as e:
                print(f"[HATA] UDP: {e}")

    def register_doctor(self, sock, addr):
        global client_counter
        with lock:
            if len(doctors) >= 2:
                sock.send("Sadece 2 doktor kabul edilir.".encode())
                sock.close()
                return
            name = f"Doktor{len(doctors)+1}"
            doctors[name] = {'socket': sock, 'patients': [], 'current': None, 'addr': addr}
            for i in range(2):
                doctors[name]['patients'].append(f"RandevuHasta{name[-1]}{i+1}")
            sock.send(f"Hoşgeldiniz {name}, {len(doctors[name]['patients'])} randevulu hasta var.".encode())
            threading.Thread(target=self.handle_doctor_commands, args=(name, sock), daemon=True).start()

    def register_patient(self, sock, addr, is_tcp):
        global client_counter
        with lock:
            if not doctors:
                msg = "Sistemde doktor yok."
                sock.send(msg.encode()) if is_tcp else sock.sendto(msg.encode(), addr)
                if is_tcp:
                    sock.close()
                return
            name = f"Hasta{client_counter+1}"
            client_counter += 1
            patients[name] = {'socket': sock, 'is_tcp': is_tcp, 'addr': addr, 'assigned_doctor': None}
            waiting_patients.put(name)
            msg = f"Hoşgeldiniz {name}"
            if is_tcp:
                sock.send(msg.encode())
                threading.Thread(target=self.handle_patient_commands, args=(name, sock), daemon=True).start()
            else:
                sock.sendto(msg.encode(), addr)

    def handle_doctor_commands(self, name, sock):
        try:
            while True:
                msg = sock.recv(BUFFER_SIZE).decode()
                if msg == "Hasta Kabul":
                    self.call_next_patient(name)
        except:
            pass

    def handle_patient_commands(self, name, sock):
        try:
            while True:
                msg = sock.recv(BUFFER_SIZE).decode()
                if msg.startswith("ACCEPT"):
                    self.patient_accept_appointment(name)
        except:
            pass

    def call_next_patient(self, doctor_name):
        doc = doctors[doctor_name]
        if doc['current']:
            self.end_appointment(doctor_name)
        next_patient = None
        if doc['patients']:
            next_patient = doc['patients'].pop(0)
            if next_patient.startswith("RandevuHasta"):
                doc['socket'].send(f"{next_patient} randevusu başlıyor...".encode())
                time.sleep(2)
                doc['socket'].send(f"{next_patient} randevusu tamamlandı.".encode())
                self.call_next_patient(doctor_name)
                return
        else:
            try:
                next_patient = waiting_patients.get_nowait()
            except queue.Empty:
                doc['socket'].send("Bekleyen hasta yok.".encode())
                if self.all_patients_done():
                    self.shutdown_system()
                return
        doc['current'] = next_patient
        patients[next_patient]['assigned_doctor'] = doctor_name
        doc['socket'].send(f"{next_patient} -> {doctor_name}".encode())
        self.send_to_patient(next_patient, f"{next_patient} -> {doctor_name}")
        threading.Thread(target=self.patient_timeout, args=(doctor_name, next_patient), daemon=True).start()

    def patient_timeout(self, doctor_name, patient_name):
        time.sleep(10)
        doc = doctors.get(doctor_name)
        patient = patients.get(patient_name)
        if doc and patient and doc['current'] == patient_name and patient['assigned_doctor'] == doctor_name:
            doc['socket'].send(f"{patient_name} cevap vermedi.".encode())
            patient['assigned_doctor'] = None
            doc['current'] = None
            waiting_patients.put(patient_name)
            self.call_next_patient(doctor_name)

    def patient_accept_appointment(self, patient_name):
        patient = patients.get(patient_name)
        if not patient:
            return
        doctor_name = patient['assigned_doctor']
        if not doctor_name:
            return
        doc = doctors.get(doctor_name)
        if not doc:
            return
        msg = f"{patient_name} {doctor_name} randevusunu kabul etti"
        doc['socket'].send(msg.encode())
        self.send_to_patient(patient_name, msg)
        self.send_to_patient(patient_name, "Geçmiş olsun")
        self.end_appointment(doctor_name)
        if self.all_patients_done():
            self.shutdown_system()

    def end_appointment(self, doctor_name):
        doc = doctors.get(doctor_name)
        if not doc:
            return
        patient_name = doc['current']
        doc['current'] = None
        if patient_name in patients:
            patient = patients.pop(patient_name)
            if patient['is_tcp']:
                try:
                    patient['socket'].close()
                except:
                    pass
            print(f"{patient_name} ayrıldı")

    def all_patients_done(self):
        return waiting_patients.empty() and not patients and all(not doc['patients'] and not doc['current'] for doc in doctors.values())

    def shutdown_system(self):
        print("[SERVER] Tüm hastalar işlendi. Sistem kapatılıyor...")
        for name, doc in doctors.items():
            try:
                doc['socket'].send("Tüm hastalar işlendi. Sistem kapatılıyor.".encode())
                doc['socket'].close()
            except:
                pass
        doctors.clear()
        patients.clear()
        waiting_patients.queue.clear()
        time.sleep(1)
        sys.exit(0)

    def send_to_patient(self, name, msg):
        patient = patients.get(name)
        if not patient:
            return
        try:
            if patient['is_tcp']:
                patient['socket'].send(msg.encode())
            else:
                self.udp_socket.sendto(msg.encode(), patient['addr'])
        except:
            pass

if __name__ == "__main__":
    Server().start()