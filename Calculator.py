
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import zipfile, os, struct, xml.etree.ElementTree as ET
import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Global storage
loaded = []

# 3MF namespace
NAMESPACE = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

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
        for m in [f for f in z.namelist() if f.startswith('3D/') and f.endswith('.model')]:
            v, t = extract_mesh_3mf(z, m)
            if v and t:
                data.append((m, v, t))
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

def volume_bbox(verts):
    xs, ys, zs = zip(*verts)
    return (max(xs)-min(xs))*(max(ys)-min(ys))*(max(zs)-min(zs)) / 1000.0

def volume_tetra(verts, tris):
    arr = np.array(verts)
    return abs(sum(np.dot(arr[a], np.cross(arr[b], arr[c]))/6.0 for a,b,c in tris)) / 1000.0

def visualize(verts, tris):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    mesh = [[verts[i] for i in tri] for tri in tris]
    ax.add_collection3d(Poly3DCollection(mesh, facecolor='skyblue', edgecolor='gray', alpha=0.5))
    xs, ys, zs = zip(*verts)
    for x in (min(xs), max(xs)):
        for y in (min(ys), max(ys)):
            ax.plot([x,x],[y,y],[min(zs),max(zs)], color='red')
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    plt.tight_layout()
    plt.show()

def recalc():
    output.config(state='normal')
    output.delete('1.0', tk.END)
    mode_val = mode.get()
    try:
        rate_bbox = float(entry_bbox.get())
        rate_tetra = float(entry_tetra.get())
    except ValueError:
        messagebox.showerror('Ошибка', 'Введите корректные цены в рублях.')
        output.config(state='disabled')
        return
    if not loaded:
        output.insert(tk.END, 'Сначала загрузите 3D файл\n')
        output.config(state='disabled')
        return
    for i,(name, verts, tris) in enumerate(loaded,1):
        if mode_val == 'bbox':
            vol = volume_bbox(verts)
            rate = rate_bbox
        else:
            vol = volume_tetra(verts, tris)
            rate = rate_tetra
        cost = vol * rate
        output.insert(tk.END, f'Объект {i}: {os.path.basename(name)}\n')
        output.insert(tk.END, f'  Объём: {vol:.2f} см³\n  Стоимость: {cost:.2f} руб.\n\n')
    output.config(state='disabled')

def on_mode_change():
    recalc()

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

def show_model():
    if not loaded:
        messagebox.showwarning('Нет данных','Загрузите файл')
        return
    for _,v,t in loaded:
        visualize(v,t)

# GUI
root = tk.Tk()
root.title('3D калькулятор')
root.geometry('500x500')
frame = tk.Frame(root, bg='#f9f9f9', padx=20, pady=20)
frame.pack(fill='both', expand=True)

tk.Label(frame, text='3D Калькулятор (.3mf / .stl)', font=('Arial',20,'bold'), bg='#f9f9f9').pack(pady=(0,10))

mode = tk.StringVar(value='bbox')
tk.Radiobutton(frame, text='Bounding Box', variable=mode, value='bbox', font=('Arial',14),
bg='#f9f9f9', fg='#7A6EB0', selectcolor='#f9f9f9', command=on_mode_change).pack(anchor='w')
tk.Radiobutton(frame, text='Tetrahedrons', variable=mode, value='tetra', font=('Arial',14),
bg='#f9f9f9', fg='#7A6EB0', selectcolor='#f9f9f9', command=on_mode_change).pack(anchor='w')

# Rates frame
rates = tk.Frame(frame, bg='#f9f9f9'); rates.pack(pady=5, fill='x')
tk.Label(rates, text='Цена bbox, руб/см³:', font=('Arial',12), bg='#f9f9f9').pack(side='left')
entry_bbox = tk.Entry(rates, width=6, font=('Arial',12)); entry_bbox.insert(0,'5'); entry_bbox.pack(side='left', padx=5)
tk.Label(rates, text='Цена tetra, руб/см³:', font=('Arial',12), bg='#f9f9f9').pack(side='left')
entry_tetra = tk.Entry(rates, width=6, font=('Arial',12)); entry_tetra.insert(0,'6'); entry_tetra.pack(side='left', padx=5)

# Buttons and output
btn_load = tk.Button(frame, text='Загрузить 3D файл', font=('Arial',12,'bold'),
bg='#7A6EB0', fg='white', command=open_file)
btn_load.pack(pady=10, fill='x')

output = scrolledtext.ScrolledText(frame, font=('Consolas',12), state='disabled')
output.pack(fill='both', expand=True, pady=5)

btn_show = tk.Button(frame, text='Показать 3D', font=('Arial',12,'bold'),
bg='#7A6EB0', fg='white', command=show_model)
btn_show.pack(pady=5, fill='x')

root.mainloop()
