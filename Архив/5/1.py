import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import struct
import xml.etree.ElementTree as ET
import numpy as np

# Global storage
loaded = []

# 3MF namespace
NAMESPACE = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

# Material densities in g/cm³
MATERIALS = {
    # ... ваш словарь материалов без изменений ...
}

# Price per gram for each material
PRICE_PER_GRAM = {
    # ... ваш словарь цен без изменений ...
}

# --- Новые константы для расчёта веса ---
PRESETS = {
    'light':  {'walls': 2, 'infill': 10.0},
    'medium': {'walls': 3, 'infill': 35.0},
    'heavy':  {'walls': 5, 'infill': 50.0},
}

CAP_HEIGHT_MM      = 0.8   # толщина дна + крышки, мм
WALL_THICKNESS_MM  = 0.4   # ширина одного периметра, мм

def extract_mesh_3mf(z, path):
    # ... без изменений ...
    pass

def parse_3mf(path):
    # ... без изменений ...
    pass

def parse_stl(path):
    # ... без изменений ...
    pass

def parse_geometry(path):
    # ... без изменений ...
    pass

def volume_bbox(verts):
    # ... по-прежнему используется как запасной вариант ...
    pass

def volume_tetra(verts, tris):
    arr = np.array(verts)
    total = 0
    for a, b, c in tris:
        total += np.dot(arr[a], np.cross(arr[b], arr[c])) / 6.0
    return abs(total) / 1000.0  # mm³→cm³

# ——— Новые вспомогательные функции ———

def caps_area(verts, tris):
    """Площадь поперечного сечения (см²), приближение через bounding box."""
    xs, ys, _ = zip(*verts)
    width_mm  = max(xs) - min(xs)
    depth_mm  = max(ys) - min(ys)
    area_mm2  = width_mm * depth_mm
    return area_mm2 / 100.0  # mm²→cm²

def perimeter_length(verts, tris):
    """Приближение длины периметра контура через периметр bounding box (см)."""
    xs, ys, _ = zip(*verts)
    width_mm  = max(xs) - min(xs)
    depth_mm  = max(ys) - min(ys)
    perim_mm  = 2*(width_mm + depth_mm)
    return perim_mm / 10.0  # mm→cm

def model_height_cm(verts):
    """Высота модели (см)."""
    _, _, zs = zip(*verts)
    height_mm = max(zs) - min(zs)
    return height_mm / 10.0

# ——— Основная логика перерасчёта ———

def recalc(*args):
    output.config(state='normal')
    output.delete('1.0', tk.END)
    if not loaded:
        output.insert(tk.END, 'Сначала загрузите модель.\n')
        output.config(state='disabled')
        return

    # выбираем материал
    material = selected_material.get()
    density = MATERIALS[material]
    price_g = PRICE_PER_GRAM[material]

    # выбираем пресет
    preset = selected_preset.get()
    params = PRESETS[preset]
    walls  = params['walls']
    infill = params['infill'] / 100.0

    mode_val = mode.get()

    for idx, (name, verts, tris) in enumerate(loaded, start=1):
        # 1) общий объём
        if mode_val == 'bbox':
            V_total = volume_bbox(verts)
        else:
            V_total = volume_tetra(verts, tris)

        # 2) крышки
        A_caps = caps_area(verts, tris)               # см²
        V_caps = A_caps * (CAP_HEIGHT_MM / 10.0)      # см³

        # 3) стенки
        L_perim = perimeter_length(verts, tris)       # см
        T_wall  = WALL_THICKNESS_MM / 10.0            # см
        H_model = model_height_cm(verts)              # см
        V_walls = L_perim * T_wall * H_model * walls  # см³

        # 4) инфилл
        V_infill = max(V_total - V_caps - V_walls, 0.0) * infill  # см³

        # 5) итоговый вес и стоимость
        weight = density * (V_caps + V_walls + V_infill)         # г
        cost   = weight * price_g                                # руб

        # вывод
        output.insert(tk.END, f'Объект {idx}: {os.path.basename(name)}\n')
        output.insert(tk.END, f'  Вес ({preset}): {weight:.2f} г\n')
        output.insert(tk.END, f'  Стоимость: {cost:.2f} руб.\n\n')

    output.config(state='disabled')

# ——— GUI ———

def on_mode_change():
    recalc()

def open_file():
    path = filedialog.askopenfilename(filetypes=[('3D Files','*.3mf *.stl')])
    if not path:
        return
    try:
        objs = parse_geometry(path)
    except Exception as e:
        messagebox.showerror('Ошибка', str(e))
        return
    loaded.clear()
    loaded.extend(objs)
    recalc()

root = tk.Tk()
root.title('3D Калькулятор')
root.geometry('520x620')

frame = tk.Frame(root, bg='#f9f9f9', padx=20, pady=20)
frame.pack(fill='both', expand=True)

tk.Label(frame, text='3D Калькулятор (.3mf / .stl)', font=('Arial', 20, 'bold'),
         bg='#f9f9f9').pack(pady=(0,10))

mode = tk.StringVar(value='tetra')
tk.Radiobutton(frame, text='Ограничивающий параллелепипед', variable=mode, value='bbox',
               font=('Arial',14), bg='#f9f9f9', fg='#7A6EB0', selectcolor='#f9f9f9',
               command=on_mode_change).pack(anchor='w')
tk.Radiobutton(frame, text='Тетраэдры', variable=mode, value='tetra',
               font=('Arial',14), bg='#f9f9f9', fg='#7A6EB0', selectcolor='#f9f9f9',
               command=on_mode_change).pack(anchor='w')

# Материал
material_frame = tk.Frame(frame, bg='#f9f9f9')
material_frame.pack(pady=(10,5), fill='x')
tk.Label(material_frame, text='Материал:', font=('Arial',12), bg='#f9f9f9').pack(side='left')
selected_material = tk.StringVar(value=list(MATERIALS.keys())[0])
tk.OptionMenu(material_frame, selected_material, *MATERIALS.keys()).pack(side='left', padx=5)
selected_material.trace_add('write', recalc)

# Пресеты
preset_frame = tk.Frame(frame, bg='#f9f9f9')
preset_frame.pack(pady=(5,10), fill='x')
tk.Label(preset_frame, text='Профиль:', font=('Arial',12), bg='#f9f9f9').pack(side='left')
selected_preset = tk.StringVar(value='medium')
tk.OptionMenu(preset_frame, selected_preset, *PRESETS.keys()).pack(side='left', padx=5)
selected_preset.trace_add('write', recalc)

btn_load = tk.Button(frame, text='Загрузить 3D файл', font=('Arial',12,'bold'),
                     bg='#7A6EB0', fg='white', command=open_file)
btn_load.pack(pady=10, fill='x')

output = scrolledtext.ScrolledText(frame, font=('Consolas',12), state='disabled')
output.pack(fill='both', expand=True, pady=5)

root.mainloop()
