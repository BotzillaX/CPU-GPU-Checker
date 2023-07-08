import os
import wmi
import subprocess
import time
import psutil
import operator
import datetime
import sqlite3
import sys

reading = "no" #either "yes" or "no" #if no, it will record/monitor your temperatures. #if yes, it will print out the content of the db file.

start_or_read = 1
if reading == "yes":
    start_or_read = 0

temperature_limiter = { #here goes the limit. what i mean is this script checks if the computer reaches cpu temperatures > or equal to 89 and or if gpu temperatures > or equal to 89. you can change the limit over here.
    "cpu": 89,
    "gpu": 89
}


def print_current_path_up_to_parent_directory():
    filepath = os.path.abspath(__file__)
    parent_directory_path = os.path.dirname(filepath)
    return parent_directory_path

if start_or_read == 0:
    import sqlite3

    def print_all_data(path_to_db):
        conn = sqlite3.connect(path_to_db)
        c = conn.cursor()

        print("\n========== System Info ==========")
        print(f"{'Time':<20} {'Path':<60} {'CPU Temp':<10} {'GPU Temp':<10}")
        print('-'*100)
        c.execute("SELECT * FROM system_info")
        system_info_rows = c.fetchall()
        for row in system_info_rows:
            time, path, cpu_temp, gpu_temp = row
            print(f"{time:<20} {path:<60} {cpu_temp:<10} {gpu_temp:<10}")

        print("\n========== Processes Info ==========")
        print(f"{'Time':<20} {'Process Name':<20} {'Memory Usage':<15} {'PID':<10}")
        print('-'*70)
        c.execute("SELECT * FROM processes")
        process_info_rows = c.fetchall()
        for idx, row in enumerate(process_info_rows):
            time, name, memory_usage, pid = row
            print(f"{time:<20} {name:<20} {memory_usage:<15} {pid:<10}")
            if (idx + 1) % 3 == 0:
                print("\n")
        
        conn.close()

    path = print_current_path_up_to_parent_directory()

    print_all_data(path+"\log.db")



if start_or_read == 1:
    def initialize_database():
        path = print_current_path_up_to_parent_directory()

        conn = sqlite3.connect(path+"\log.db")  
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS system_info
            (time TEXT, path TEXT, cpu_temp REAL, gpu_temp REAL)
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS processes
            (time TEXT, name TEXT, memory_usage REAL, pid INTEGER)
        ''')
        conn.commit()
        return conn, c


    def save_data_to_db(conn, c, system_info, processes):
        system_data = (system_info['time'], system_info['path'], system_info['cpu_temp'], system_info['gpu_temp'])
        c.execute('INSERT INTO system_info VALUES (?,?,?,?)', system_data)
        print(f"Saved system data: {system_data}")

        for process in processes:
            process_data = (system_info['time'], process['name'], process['memory_info'], process['pid'])
            c.execute('INSERT INTO processes VALUES (?,?,?,?)', process_data)
            print(f"Saved process data: {process_data}")
        conn.commit()


    def print_current_path_without_extension():
        filepath = os.path.abspath(__file__)
        basepath = os.path.splitext(filepath)[0]
        return f"{basepath}"

    def get_cpu_temperature():
        w = wmi.WMI(namespace="root\\OpenHardwareMonitor")
        temperature_info = w.Sensor()
        for sensor in temperature_info:
            if sensor.SensorType == u'Temperature' and "cpu" in sensor.Identifier.lower():
                return sensor.Value
        return None

    def get_gpu_temperature():
        try:
            nvidia_smi = "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
            gpu_temp = subprocess.check_output(nvidia_smi, shell=True).decode().strip()
            return gpu_temp
        except Exception as e:
            print(f"Couldn't get GPU temperature: {e}")
            return None

    def print_system_info():
        cpu_temp = get_cpu_temperature()
        gpu_temp = get_gpu_temperature()
        system_info = {
            'time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'path': print_current_path_without_extension(),
            'cpu_temp': cpu_temp,
            'gpu_temp': gpu_temp
        }
        return system_info

    def get_top_processes():
        processes = []
        for proc in psutil.process_iter(['name', 'memory_info', 'pid']):
            try:
                processes.append({
                    'name': proc.info['name'],
                    'memory_info': proc.info['memory_info'].rss / 1024 / 1024,
                    'pid': proc.pid
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        sorted_by_memory = sorted(processes, key=operator.itemgetter('memory_info'), reverse=True)
        top_memory_processes = sorted_by_memory[:3]
        return top_memory_processes

    def log_system_info():
        system_info = print_system_info()
        processes = get_top_processes()
        return system_info, processes

    def main():
        conn, c = initialize_database()
        print("Database initialized.")
        while True:
            cpu_temp = get_cpu_temperature()
            gpu_temp = get_gpu_temperature()
            if cpu_temp:
                print(f"Current CPU temperature: {cpu_temp}")
                print(f"Current GPU temperature: {gpu_temp}")
                if int(cpu_temp) >= temperature_limiter['cpu'] or int(gpu_temp) >= temperature_limiter['gpu']:
                    print("CPU temperature above threshold, logging information...")
                    system_info, processes = log_system_info()
                    save_data_to_db(conn, c, system_info, processes)
                else:
                    print("CPU temperature below threshold, not logging information.")
            else:
                print("Could not get CPU temperature.")
            time.sleep(1)

    if __name__ == '__main__':
        main()
