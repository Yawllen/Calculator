import tkinter as tk
from tkinter import filedialog, messagebox
import zipfile
import xml.etree.ElementTree as ET
import os

def parse_3mf_multi(file_path):
    object_data = []

    with zipfile.ZipFile(file_path, 'r') as z:
        ns = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

        # Объекты из Orca-style
        model_files = [f for f in z.namelist() if f.startswith('3D/Objects/') and f.endswith('.model')]

        # Если Orca-объекты найдены
        if model_files:
            for model_file in model_files:
                vertices = []
                try:
                    with z.open(model_file) as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        for mesh in root.findall(".//ns:mesh", ns):
                            for vertex in mesh.findall(".//ns:vertex", ns):
                                x = float(vertex.attrib['x'])
                                y = float(vertex.attrib['y'])
                                z = float(vertex.attrib['z'])
                                vertices.append((x, y, z))
                    if vertices:
                        object_data.append((model_file, vertices))
                except Exception:
                    continue
        else:
            # Пытаемся прочитать стандартную модель
            try:
                with z.open('3D/3dmodel.model') as f:
                    vertices = []
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for mesh in root.findall(".//ns:mesh", ns):
                        for vertex in mesh.findall(".//ns:vertex", ns):
                            x = float(vertex.attrib['x'])
                            y = float(vertex.attrib['y'])
                            z = float(vertex.attrib['z'])
                            vertices.append((x, y, z))
                    if vertices:
                        object_data.append(('3D/3dmodel.model', vertices))
            except KeyError:
                pass

    return object_data

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
    cost = volume_cm3 * 7

    return round(volume_cm3, 2), round(cost, 2)

def open_file():
    file_path = filedialog.askopenfilename(filetypes=[("3MF Files", "*.3mf")])
    if file_path:
        try:
            objects = parse_3mf_multi(file_path)
            if not objects:
                raise ValueError("Файл не содержит подходящей геометрии.")

            result = f"Найдено деталей: {len(objects)}\n\n"
            for index, (name, vertices) in enumerate(objects, 1):
                volume, cost = calculate_cost(vertices)
                result += f"Деталь {index} ({os.path.basename(name)}):\n"
                result += f"  Объём: {volume} см³\n"
                result += f"  Стоимость: {cost} руб.\n\n"

            result_label.config(text=result.strip())
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обработать файл: {e}")

root = tk.Tk()
root.title("Калькулятор 3D-печати")

frame = tk.Frame(root, padx=20, pady=20)
frame.pack()

btn = tk.Button(frame, text="Выбрать .3mf файл", command=open_file)
btn.pack(pady=10)

result_label = tk.Label(frame, text="Здесь будет результат", justify="left", anchor="w")
result_label.pack()

root.mainloop()
