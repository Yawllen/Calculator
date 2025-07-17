
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os, struct, zipfile, xml.etree.ElementTree as ET
import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Global
loaded = []
NAMESPACE = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

# Материалы
MATERIALS = {
    "Enduse PETG": 1.27,
    "Proto PLA": 1.24,
    "Enduse ABS": 1.04,
    "Fiberpart PA CF30": 1.15,
    "Другой материал": 1.00
}

PRICE_PER_GRAM = {
    "Enduse PETG": 2.33,
    "Proto PLA": 3.07,
    "Enduse ABS": 2.4,
    "Fiberpart PA CF30": 10.4,
    "Другой материал": 2.0
}

# FDM параметры
wall_count = 2
wall_width = 0.4
layer_height = 0.2
top_bottom_layers = 4

def extract_mesh_3mf(z, path):
    verts, tris = [], []
    tree = ET.parse(z.open(path))
    root = tree.getroot()
    for mesh in root.findall('.//ns:mesh', NAMESPACE):
        vlist = mesh.find('ns:vertices', NAMESPACE)
        tlist = mesh.find('ns:triangles', NAMESPACE)
        if vlist:
            for v in vlist.findall('ns:vertex', NAMESPACE):
                verts.append((float(v.attrib['x']), float(v.attrib['y']), float(v.attrib['z'])))
        if tlist:
            for t in tlist.findall('ns:triangle', NAMESPACE):
                tris.append((int(t.attrib['v1']), int(t.attrib['v2']), int(t.attrib['v3'])))
    return verts, tris

def parse_3mf(path):
    data = []
    with zipfile.ZipFile(path) as z:
        for f in z.namelist():
            if f.startswith('3D/') and f.endswith('.model'):
                v, t = extract_mesh_3mf(z, f)
                if v and t:
                    data.append((f, v, t))
    return data

def parse_stl(path):
    verts, tris, idx_map = [], [], {}
    with open(path, 'rb') as f:
        f.seek(80)
        count = struct.unpack('<I', f.read(4))[0]
        for _ in range(count):
            f.read(12)
            face = []
            for _ in range(3):
                xyz = struct.unpack('<fff', f.read(12))
                if xyz not in idx_map:
                    idx_map[xyz] = len(verts)
                    verts.append(xyz)
                face.append(idx_map[xyz])
            tris.append(tuple(face))
            f.read(2)
    return [('STL model', verts, tris)]

def parse_geometry(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.3mf': return parse_3mf(path)
    if ext == '.stl': return parse_stl(path)
    raise ValueError('Only .3mf and .stl supported')

def volume_tetra(verts, tris):
    arr = np.array(verts)
    return abs(sum(np.dot(arr[a], np.cross(arr[b], arr[c]))/6.0 for a,b,c in tris)) / 1000.0

def bbox(verts):
    xs, ys, zs = zip(*verts)
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)

def surface_area_bbox(xmin,xmax,ymin,ymax,zmin,zmax):
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    return 2 * (dx*dy + dx*dz + dy*dz) / 100.0

def xy_area_bbox(xmin,xmax,ymin,ymax):
    return (xmax - xmin) * (ymax - ymin) / 100.0

def surface_area_mesh(verts, tris):
    area = 0.0
    for a, b, c in tris:
        v1 = np.array(verts[b]) - np.array(verts[a])
        v2 = np.array(verts[c]) - np.array(verts[a])
        area += np.linalg.norm(np.cross(v1, v2)) / 2
    return area / 100.0  # мм² → см²

def recalc(*args):
    output.config(state='normal')
    output.delete('1.0', tk.END)
    if not loaded:
        output.insert(tk.END, 'Сначала загрузите модель.\n')
        output.config(state='disabled')
        return
    try:
        infill = float(entry_infill.get())
    except ValueError:
        messagebox.showerror('Ошибка', 'Введите корректный % заполнения.')
        output.config(state='disabled')
        return

    material = selected_material.get()
    density = MATERIALS[material]
    price = PRICE_PER_GRAM[material]

    for idx, (name, verts, tris) in enumerate(loaded, start=1):
        V_model = volume_tetra(verts, tris)
        xmin,xmax,ymin,ymax,zmin,zmax = bbox(verts)
        shell_area = surface_area_mesh(verts, tris)
        xy_area = xy_area_bbox(xmin,xmax,ymin,ymax)

        V_shell = shell_area * wall_count * wall_width / 10.0
        V_top_bottom = xy_area * top_bottom_layers * layer_height / 10.0

        shell_total = V_shell + V_top_bottom
        if shell_total > V_model * 0.6:
            scale = (V_model * 0.6) / shell_total
            V_shell *= scale
            V_top_bottom *= scale

        V_infill = max(0, V_model - V_shell - V_top_bottom) * (infill / 100.0)
        V_total = V_shell + V_top_bottom + V_infill

        weight = V_total * density
        cost = weight * price

        output.insert(tk.END, f'Объект {idx}: {os.path.basename(name)}\n')
        output.insert(tk.END, f'  Объём модели: {V_model:.2f} см³\n')
        output.insert(tk.END, f'  Вес: {weight:.2f} г\n')
        output.insert(tk.END, f'  Стоимость: {cost:.2f} руб.\n\n')
    output.config(state='disabled')
def open_file():
    path = filedialog.askopenfilename(filetypes=[('3D Files','*.3mf *.stl')])
    if not path: return
    try:
        objs = parse_geometry(path)
    except Exception as e:
        messagebox.showerror('Ошибка', str(e))
        return
    loaded.clear(); loaded.extend(objs)
    recalc()

def visualize(verts, tris):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    mesh = [[verts[i] for i in tri] for tri in tris]
    ax.add_collection3d(Poly3DCollection(mesh, facecolor='skyblue', edgecolor='gray', alpha=0.5))
    xs, ys, zs = zip(*verts)
    ax.set_xlim(min(xs), max(xs))
    ax.set_ylim(min(ys), max(ys))
    ax.set_zlim(min(zs), max(zs))
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()

def show_model():
    if not loaded:
        messagebox.showwarning('Нет модели','Загрузите файл')
        return
    for _,v,t in loaded:
        visualize(v,t)

root = tk.Tk()
root.title('3D калькулятор (PETG, FDM)')
root.geometry('500x600')
frame = tk.Frame(root, bg='#f9f9f9', padx=20, pady=20)
frame.pack(fill='both', expand=True)
tk.Label(frame, text='3D Калькулятор (.3mf / .stl)', font=('Arial',20,'bold'), bg='#f9f9f9').pack(pady=(0,10))

mode = tk.StringVar(value='tetra')
tk.Radiobutton(frame, text='Ограничивающий\nпараллелепипед', variable=mode, value='bbox', font=('Arial',14), bg='#f9f9f9', fg='#7A6EB0').pack(anchor='w')
tk.Radiobutton(frame, text='Тетраэдры', variable=mode, value='tetra', font=('Arial',14), bg='#f9f9f9', fg='#7A6EB0').pack(anchor='w')

material_frame = tk.Frame(frame, bg='#f9f9f9')
material_frame.pack(pady=(5,5), fill='x')
tk.Label(material_frame, text='Материал:', font=('Arial',12), bg='#f9f9f9').pack(side='left')
selected_material = tk.StringVar(value='Enduse PETG')
material_menu = tk.OptionMenu(material_frame, selected_material, *MATERIALS.keys())
material_menu.config(font=('Arial',12), bg='white')
material_menu.pack(side='left', padx=5)
selected_material.trace_add('write', recalc)

infill_frame = tk.Frame(frame, bg='#f9f9f9'); infill_frame.pack(pady=(5,10), fill='x')
tk.Label(infill_frame, text='Заполнение (%):', font=('Arial',12), bg='#f9f9f9').pack(side='left')
entry_infill = tk.Entry(infill_frame, width=6, font=('Arial',12)); entry_infill.insert(0,'10'); entry_infill.pack(side='left', padx=5)
entry_infill.bind('<KeyRelease>', lambda e: recalc())

btn_load = tk.Button(frame, text='Загрузить 3D файл', font=('Arial',12,'bold'), bg='#7A6EB0', fg='white', command=open_file)
btn_load.pack(pady=10, fill='x')

output = scrolledtext.ScrolledText(frame, font=('Consolas',12), state='disabled')
output.pack(fill='both', expand=True, pady=5)

btn_show = tk.Button(frame, text='Показать 3D', font=('Arial',12,'bold'), bg='#7A6EB0', fg='white', command=show_model)
btn_show.pack(pady=5, fill='x')

root.mainloop()
