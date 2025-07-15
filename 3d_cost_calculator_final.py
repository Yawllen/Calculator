
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import zipfile
import xml.etree.ElementTree as ET
import os
import struct

NAMESPACE = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

def extract_vertices_from_model(zip_file, model_path):
    vertices = []
    with zip_file.open(model_path) as f:
        tree = ET.parse(f)
        root = tree.getroot()
        for mesh in root.findall(".//ns:mesh", NAMESPACE):
            for vertex in mesh.findall(".//ns:vertex", NAMESPACE):
                x = float(vertex.attrib['x'])
                y = float(vertex.attrib['y'])
                z = float(vertex.attrib['z'])
                vertices.append((x, y, z))
    return vertices

def parse_3mf_multi(file_path):
    object_data = []
    with zipfile.ZipFile(file_path, 'r') as z:
        model_files = [f for f in z.namelist() if f.startswith('3D/') and f.endswith('.model')]
        for model_file in model_files:
            try:
                vertices = extract_vertices_from_model(z, model_file)
                if vertices:
                    object_data.append((model_file, vertices))
            except Exception as e:
                print(f"Ошибка при разборе {model_file}: {e}")
    return object_data

def parse_stl(file_path):
    vertices = set()
    try:
        with open(file_path, 'rb') as f:
            header = f.read(80)
            num_triangles = struct.unpack('<I', f.read(4))[0]
            expected_size = 84 + num_triangles * 50
            f.seek(0, 2)
            file_size = f.tell()
            if file_size == expected_size:
                f.seek(84)
                for _ in range(num_triangles):
                    f.read(12)
                    v1 = struct.unpack('<fff', f.read(12))
                    v2 = struct.unpack('<fff', f.read(12))
                    v3 = struct.unpack('<fff', f.read(12))
                    vertices.update([v1, v2, v3])
                    f.read(2)
                return list(vertices)
    except Exception as e:
        print(f"[!] Ошибка при чтении бинарного STL: {e}")

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                parts = line.strip().split()
                if parts[:1] == ['vertex'] and len(parts) == 4:
                    try:
                        v = tuple(map(float, parts[1:]))
                        vertices.add(v)
                    except ValueError:
                        continue
        return list(vertices)
    except Exception as e:
        print(f"[!] Ошибка при чтении ASCII STL: {e}")
        return []

def parse_obj(file_path):
    vertices = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.strip().split()
                if len(parts) == 4:
                    try:
                        v = tuple(map(float, parts[1:]))
                        vertices.append(v)
                    except ValueError:
                        continue
    return vertices

def parse_vertices_from_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".3mf":
        return parse_3mf_multi(file_path)
    elif ext == ".stl":
        vertices = parse_stl(file_path)
        return [("STL модель", vertices)] if vertices else []
    elif ext == ".obj":
        vertices = parse_obj(file_path)
        return [("OBJ модель", vertices)] if vertices else []
    else:
        raise ValueError(f"Неподдерживаемый формат файла: {ext}")

def calculate_cost(vertices):
    if not vertices:
        raise ValueError("Ни один объект не содержит координат.")
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dz = max(zs) - min(zs)
    volume_mm3 = dx * dy * dz
    volume_cm3 = volume_mm3 / 1000.0
    cost = volume_cm3 * 4.5  # новая цена
    return round(volume_cm3, 2), round(cost, 2)

def open_file():
    file_path = filedialog.askopenfilename(filetypes=[("3D Files", "*.3mf *.stl *.obj")])
    if file_path:
        try:
            objects = parse_vertices_from_file(file_path)
            if not objects:
                raise ValueError("Файл не содержит подходящей геометрии.")
            result = f"📦 Найдено объектов: {len(objects)}\n\n"
            for index, (name, vertices) in enumerate(objects, 1):
                volume, cost = calculate_cost(vertices)
                result += f"🔹 Объект {index} — {os.path.basename(name)}\n"
                result += f"    Объём: {volume} см³\n"
                result += f"    Стоимость: {cost} руб.\n\n"
            result_text.configure(state='normal')
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, result.strip())
            result_text.configure(state='disabled')
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обработать файл:\n{e}")

root = tk.Tk()
root.title("Калькулятор 3D-печати")
root.geometry("600x500")
root.resizable(False, False)

frame = tk.Frame(root, padx=20, pady=20, bg="#f2f2f2")
frame.pack(fill=tk.BOTH, expand=True)

title_label = tk.Label(frame, text="3D Калькулятор стоимости печати", font=("Helvetica", 16, "bold"), bg="#f2f2f2")
title_label.pack(pady=(0, 10))

btn = tk.Button(frame, text="📂 Выбрать 3D-файл (.3mf / .stl / .obj)", command=open_file, font=("Helvetica", 12), bg="#4CAF50", fg="white", padx=10, pady=5)
btn.pack(pady=10)

result_text = scrolledtext.ScrolledText(frame, width=70, height=20, wrap=tk.WORD, font=("Consolas", 10), state='disabled')
result_text.pack(pady=10, fill=tk.BOTH, expand=True)

root.mainloop()
