import cv2
import face_recognition
import numpy as np
import sqlite3
from datetime import datetime
import geocoder
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
import time
COLORS = {
    "primary": "#1abc9c",
    "secondary": "#3498db",
    "dark": "#2c3e50", 
    "light": "#ecf0f1",
    "danger": "#e74c3c",
    "warning": "#f39c12",
    "success": "#2ecc71"
}  
DB_NAME = 'attendance3.db'
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT    NOT NULL UNIQUE,
            encoding  BLOB    NOT NULL
        )
    """)                                                                  
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id  INTEGER  NOT NULL,
            timestamp    DATETIME NOT NULL,
            latitude     REAL,
            longitude    REAL,
            FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()
def add_employee(name, encoding):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO employees (name, encoding) VALUES (?, ?)",
            (name, encoding.tobytes())
        )
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", f"Employee '{name}' already exists!")
        return None
    finally:
        conn.close()
class FaceAttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("✨ IOCL Face Attendance System ✨")
        self.root.geometry("1200x800")
        self.root.configure(bg=COLORS["light"])
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=COLORS["light"])
        style.configure('TNotebook', background=COLORS["light"])
        style.configure('TNotebook.Tab', font=('Helvetica', 11, 'bold'))
        style.configure('TLabel', background=COLORS["light"], font=('Helvetica', 10))
        style.configure('Header.TLabel', background=COLORS["dark"], foreground='white', font=('Helvetica', 16, 'bold'))
        style.configure('TButton', font=('Helvetica', 10, 'bold'), padding=6)
        self.root.option_add("*TButton.Background", COLORS['primary'])
        self.root.option_add("*TButton.Foreground", "white")
        self.root.option_add("*TNotebook.Tab.Background", COLORS['secondary'])
        self.root.option_add("*TNotebook.Tab.Foreground", "white")
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        self.register_tab = ttk.Frame(self.notebook)
        self.attendance_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.register_tab, text="➕ Register Employee")
        self.notebook.add(self.attendance_tab, text="📸 Live Attendance")

        self.setup_register_tab()
        self.setup_attendance_tab()

        self.known_faces = []
        self.known_names = []
        self.known_ids = []
        self.last_marked = {}

        self.load_faces()

    def setup_register_tab(self):
        frame = ttk.LabelFrame(self.register_tab, text="New Employee Registration", padding=20)
        frame.pack(padx=30, pady=30, fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Employee Name:").pack(anchor=tk.W, pady=5)
        self.name_entry = ttk.Entry(frame, font=('Helvetica', 12))
        self.name_entry.pack(fill=tk.X, pady=5)

        self.register_button = ttk.Button(frame, text="📷 Capture and Register", command=self.add_new_employee)
        self.register_button.pack(pady=15)

        self.preview_label = ttk.Label(frame, text="Camera preview will appear here")
        self.preview_label.pack(pady=10)

        self.video_capture = cv2.VideoCapture(0)
        if not self.video_capture.isOpened():
            messagebox.showerror("Error", "Could not access camera")
            self.root.destroy()
            return

        self.update_preview()

    def setup_attendance_tab(self):
        frame = ttk.LabelFrame(self.attendance_tab, text="Live Attendance", padding=10)
        frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        self.video_label = ttk.Label(frame)
        self.video_label.pack(fill=tk.BOTH, expand=True)
        self.status_label = ttk.Label(frame, text="✅ System Ready", font=('Helvetica', 11, 'bold'), background=COLORS['success'], foreground='white')
        self.status_label.pack(fill=tk.X, pady=10)
        self.last_attendance_label = ttk.Label(frame, text="Last Attendance: None", font=('Helvetica', 10), background=COLORS['light'])
        self.last_attendance_label.pack(fill=tk.X, pady=5)
        self.root.after(1000, self.update_video)

    def update_preview(self):
        ret, frame = self.video_capture.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=img.resize((400, 300)))
            self.preview_label.imgtk = imgtk
            self.preview_label.configure(image=imgtk)
        self.root.after(200, self.update_preview)

    def load_faces(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        self.known_faces.clear()
        self.known_names.clear()
        self.known_ids.clear()

        c.execute("SELECT id, name, encoding FROM employees")
        for (employee_id, name, encoding_bytes) in c.fetchall():
            encoding = np.frombuffer(encoding_bytes, dtype=np.float64)
            self.known_faces.append(encoding)
            self.known_names.append(name)
            self.known_ids.append(employee_id)
        conn.close()

    def add_new_employee(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Input Error", "Please enter a name.")
            return

        ret, frame = self.video_capture.read()
        if not ret:
            messagebox.showerror("Error", "Failed to capture image from camera.")
            return

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)

        if len(face_locations) != 1:
            messagebox.showwarning("Error", "Please ensure exactly one face is visible.")
            return

        face_encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
        new_id = add_employee(name, face_encoding)
        if new_id:
            self.load_faces()
            messagebox.showinfo("Success", f"Employee '{name}' added successfully.")
            self.name_entry.delete(0, tk.END)

    def update_video(self):
        ret, frame = self.video_capture.read()
        if ret:
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4
                matches = face_recognition.compare_faces(self.known_faces, face_encoding)
                name = "Unknown"

                if True in matches:
                    first_match_index = matches.index(True)
                    name = self.known_names[first_match_index]
                    employee_id = self.known_ids[first_match_index]

                    now = time.time()
                    last_time = self.last_marked.get(employee_id, 0)
                    if now - last_time > 30:
                        self.mark_attendance(employee_id, name)
                        self.last_marked[employee_id] = now
                        self.status_label.config(text=f"✅ Marked: {name}", background=COLORS['success'])
                        self.last_attendance_label.config(text=f"🕒 Last: {name} at {datetime.now().strftime('%H:%M:%S')}")

                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                font = cv2.FONT_HERSHEY_DUPLEX
                cv2.putText(frame, name, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

            cv2.putText(frame, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        (10, frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)

        self.root.after(10, self.update_video)

    def get_current_location(self):
        for _ in range(3):
            try:
                g = geocoder.ip('me')
                if g.ok:
                    return g.latlng
            except Exception as e:
                print("Location error:", e)
            time.sleep(1)
        return None, None

    def mark_attendance(self, employee_id, name):
        timestamp = datetime.now()
        lat, lon = self.get_current_location()

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO attendance (employee_id, timestamp, latitude, longitude)
                VALUES (?, ?, ?, ?)
            """, (employee_id, timestamp, lat, lon))
            conn.commit()
        except Exception as e:
            print("Attendance error:", e)
        finally:
            conn.close()

    def on_close(self):
        if hasattr(self, 'video_capture') and self.video_capture.isOpened():
            self.video_capture.release()
        self.root.destroy()

if __name__ == "__main__":
    try:
        init_db()
        root = tk.Tk()
        app = FaceAttendanceApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_close)
        root.mainloop()
    except Exception as e:
        print("Error occurred:", str(e))
        input("Press Enter to exit...")



