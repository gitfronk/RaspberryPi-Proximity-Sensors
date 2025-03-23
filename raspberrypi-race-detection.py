import socket
import time
import threading
import RPi.GPIO as GPIO
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import csv
import os
from datetime import datetime

# --- GPIO setup ---
SENSOR_PIN = 17
PORT = 5000
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSOR_PIN, GPIO.IN)

# --- Variabili globali ---
travel_times = []
timestamps = []
pilota = None
is_running = False
stop_requested = False
leaderboard = []
previous_order = {}

# --- Sensore e comunicazione ---
def wait_for_object():
    while not stop_requested:
        if GPIO.input(SENSOR_PIN) == GPIO.LOW:
            return time.time()
        time.sleep(0.01)
    return None

def receive_timestamp():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', PORT))
        s.listen(1)
        conn, addr = s.accept()
        with conn:
            data = conn.recv(1024)
            if not data:
                return None
            return float(data.decode())

# --- Classifica ---
def aggiorna_tabella_classifica():
    global previous_order
    old_positions = previous_order.copy()

    for row in leaderboard_table.get_children():
        leaderboard_table.delete(row)

    for i, (p, t) in enumerate(leaderboard):
        dist_prev = "-"
        dist_first = "-"
        if i > 0:
            dist_prev = f"+{round(t - leaderboard[i - 1][1], 3)}s"
        if i >= 1:
            dist_first = f"+{round(t - leaderboard[0][1], 3)}s"

        previous_rank = old_positions.get(p, i)
        change = previous_rank - i
        arrow = "-"
        tag = ""
        if change > 0:
            arrow = "↑"
            tag = "up"
        elif change < 0:
            arrow = "↓"
            tag = "down"

        if i == 0:
            tag = "first"

        leaderboard_table.insert("", "end", values=(i + 1, p, round(t, 3), dist_prev, dist_first, arrow), tags=(tag,))

    previous_order = {p: i for i, (p, _) in enumerate(leaderboard)}

def carica_classifica():
    global leaderboard
    filename = classifica_filename_entry.get().strip() or 'classifica.csv'
    if os.path.exists(filename):
        with open(filename, mode='r') as f:
            reader = csv.reader(f)
            next(reader)  # intestazione
            leaderboard = [(row[1], float(row[2])) for row in reader]
        aggiorna_tabella_classifica()

def carica_classifica_da_file():
    global leaderboard
    file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
    if not file_path:
        return
    with open(file_path, mode='r') as f:
        reader = csv.reader(f)
        next(reader)
        leaderboard = [(row[1], float(row[2])) for row in reader]
    classifica_filename_entry.delete(0, tk.END)
    classifica_filename_entry.insert(0, file_path)
    aggiorna_tabella_classifica()

def aggiorna_classifica_su_file():
    filename = classifica_filename_entry.get().strip() or 'classifica.csv'
    with open(filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Posizione", "Pilota", "Tempo (s)", "Dist. prec.", "Dist. 1°"])
        for i, (p, t) in enumerate(leaderboard):
            dist_prev = "-"
            dist_first = "-"
            if i > 0:
                dist_prev = f"+{round(t - leaderboard[i - 1][1], 3)}s"
            if i >= 1:
                dist_first = f"+{round(t - leaderboard[0][1], 3)}s"
            writer.writerow([i + 1, p, round(t, 3), dist_prev, dist_first])

def reset_classifica():
    global leaderboard
    if messagebox.askyesno("Reset Classifica", "Sei sicuro di voler cancellare la classifica?"):
        leaderboard = []
        aggiorna_tabella_classifica()
        filename = classifica_filename_entry.get().strip() or 'classifica.csv'
        if os.path.exists(filename):
            os.remove(filename)
        print("Classifica resettata.")
        messagebox.showinfo("Classifica", "Classifica resettata con successo.")

# --- Logica di gara ---
def run_race():
    global is_running, stop_requested
    t_start = receive_timestamp()
    if stop_requested or not t_start:
        reset_ui()
        return

    t_end = wait_for_object()
    if not t_end:
        reset_ui()
        return

    travel_time = t_end - t_start
    print(f"[{pilota}] Tempo: {travel_time:.3f} s")
    travel_times.append(travel_time)
    timestamps.append(time.time())
        leaderboard.append((pilota, travel_time))
    leaderboard.sort(key=lambda x: x[1])
    aggiorna_tabella_classifica()
    aggiorna_classifica_su_file()
    is_running = False
    reset_ui()

# --- Controllo pulsante Start/Stop ---
def start_or_cancel():
    global pilota, is_running, stop_requested, travel_times, timestamps
    if not is_running:
        name = entry_name.get().strip()
        if not name:
            messagebox.showerror("Errore", "Inserisci il nome del pilota!")
            return
        pilota = name
        travel_times = []
        timestamps = []
        stop_requested = False
        is_running = True
        entry_name.config(state='disabled')
        start_button.config(text="Stop")
        threading.Thread(target=run_race, daemon=True).start()
    else:
        stop_requested = True
        print("[\U0001F6D1] Gara interrotta dall'utente.")
        is_running = False
        reset_ui()

# --- Reset interfaccia ---
def reset_ui():
    entry_name.config(state='normal')
    entry_name.delete(0, tk.END)
    start_button.config(text="Start")

# --- GUI Setup ---
root = tk.Tk()
root.title("Rilevamento Tempo - Raspberry B")

frame_input = tk.Frame(root)
frame_input.pack(padx=10, pady=5)

tk.Label(frame_input, text="Nome del pilota:").pack(side=tk.LEFT)
entry_name = tk.Entry(frame_input)
entry_name.pack(side=tk.LEFT, padx=5)

start_button = tk.Button(root, text="Start", command=start_or_cancel)
start_button.pack(pady=10)

frame_classifica = tk.Frame(root)
frame_classifica.pack(padx=10, pady=5)

tk.Label(frame_classifica, text="Classifica Migliori Tempi").pack()

columns = ("Posizione", "Pilota", "Tempo (s)", "Dist. prec.", "Dist. 1°", "Movimento")
canvas = tk.Canvas(frame_classifica)
scrollbar = ttk.Scrollbar(frame_classifica, orient="vertical", command=canvas.yview)
scrollable_frame = tk.Frame(canvas)

scrollable_frame.bind(
    "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

leaderboard_table = ttk.Treeview(scrollable_frame, columns=columns, show='headings', height=20)
for col in columns:
    leaderboard_table.heading(col, text=col)
leaderboard_table.tag_configure("up", background="#d4fcd4")  # verde
leaderboard_table.tag_configure("down", background="#fcd4d4")
leaderboard_table.tag_configure("first", background="#e0ccff")  # viola per primo  # rosso
leaderboard_table.pack(fill="both", expand=True)

reset_button = tk.Button(root, text="Reset Classifica", command=reset_classifica)
reset_button.pack(pady=5)
carica_button = tk.Button(root, text="Carica Classifica", command=carica_classifica_da_file)
carica_button.pack(pady=5)

# --- Campo per il nome file classifica ---
frame_filename = tk.Frame(root)
frame_filename.pack(padx=10, pady=5)

tk.Label(frame_filename, text="Nome file classifica:").pack(side=tk.LEFT)
classifica_filename_entry = tk.Entry(frame_filename)
classifica_filename_entry.insert(0, "classifica.csv")
classifica_filename_entry.pack(side=tk.LEFT, padx=5)

carica_classifica()

root.mainloop()

GPIO.cleanup()
