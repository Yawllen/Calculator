import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os, struct, zipfile, xml.etree.ElementTree as ET
import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import time

"""
РЕФАКТОРИНГ ТОЛЬКО БЛОКОВ СЧИТЫВАНИЯ И ВЫЧИСЛЕНИЙ.
GUI/верстка минимально дополнены переключателями режимов, как просили:
- Чекбокс «Быстрый объём (без стенок/крышек)» — включает быстрый путь расчёта объёма.
- Чекбокс «Потоковый STL» — включает потоковый подсчёт объёма STL без построения меша (когда есть путь к файлу).
- Таймер: в конце вывода показывается время расчёта.

Основные вычислительные улучшения:
- 3MF: учёт transform для <build><item> и <component>, учёт unit (mm/inch/...).
- «Детерминантный» быстрый путь для объёма 3MF: объём базовой сетки × |det(M3x3)| × unit_scale^3 → см³ (без трансформации всех вершин).
- STL: потоковый объём прямо при чтении файла (без карты вершин) — по запросу чекбоксом.
- Векторизация numpy: объём (тетраэдры), площадь, bbox. Кэш numpy-массивов в loaded.
"""

# Global
loaded = []  # элементы вида: (name, V_np[*,3], T_np[*,3], vol_fast_cm3, src)
NAMESPACE = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

# Материалы
MATERIALS = {
    "Sealant TPU93": 1.20,
    "Fiberpart ABS G4": 1.04,
    "Fiberpart TPU C5": 1.20,
    "Fiberpart ABSPA G8": 1.10,
    "Fiberpart TPU G30": 1.20,
    "Enduse SBS": 1.04,
    "Enduse ABS": 1.04,
    "Enduse PETG": 1.27,
    "Enduse PP": 0.90,
    "Proto PLA": 1.24,
    "ContiFiber CPA": 1.15,
    "Sealant SEBS": 1.04,
    "Sealant TPU": 1.20,
    "Proto PVA": 1.19,
    "Enduse-PA": 1.15,
    "Enduse-TPU D70": 1.20,
    "Fiberpart ABS G13": 1.04,
    "Fiberpart PP G": 0.90,
    "Fiberpart PP G30": 0.90,
    "Enduse PC": 1.20,
    "Fiberpart PA12 G12": 1.01,
    "Metalcast-316L": 8.00,
    "Fiberpart PC G20": 1.20,
    "Fiberpart PA G30": 1.15,
    "Enduse TPU D60": 1.20,
    "Sealant TPU A90": 1.20,
    "Sealant TPU A70": 1.20,
    "Fiberpart PA CF30": 1.15,
    "Другой материал": 1.00,
}

PRICE_PER_GRAM = {
    "Sealant TPU93": 3.75,
    "Fiberpart ABS G4": 3.07,
    "Fiberpart TPU C5": 5.6,
    "Fiberpart ABSPA G8": 4.0,
    "Fiberpart TPU G30": 4.0,
    "Enduse SBS": 2.4,
    "Enduse ABS": 2.4,
    "Enduse PETG": 2.33,
    "Enduse PP": 8.08,
    "Proto PLA": 3.07,
    "ContiFiber CPA": 200.0,
    "Sealant SEBS": 5.2,
    "Sealant TPU": 5.98,
    "Proto PVA": 9.5,
    "Enduse-PA": 3.0,
    "Enduse-TPU D70": 3.99,
    "Fiberpart ABS G13": 6.65,
    "Fiberpart PP G": 3.3,
    "Fiberpart PP G30": 3.31,
    "Enduse PC": 0.0,
    "Fiberpart PA12 G12": 7.24,
    "Metalcast-316L": 16.0,
    "Fiberpart PC G20": 2.6,
    "Fiberpart PA G30": 7.9,
    "Enduse TPU D60": 1.9,
    "Sealant TPU A90": 2.6,
    "Sealant TPU A70": 6.4,
    "Fiberpart PA CF30": 10.4,
    "Другой материал": 2.0,
}
# FDM параметры (как было)
wall_count = 2
wall_width = 0.4
layer_height = 0.2
top_bottom_layers = 4

# --------------------------
# 3MF ЧТЕНИЕ С УЧЁТОМ ТРАНСФОРМ И UNIT + БЫСТРЫЙ ОБЪЁМ
# --------------------------

def _unit_to_mm(unit_str: str) -> float:
    unit = (unit_str or 'millimeter').strip().lower()
    return {
        'micron': 0.001,
        'millimeter': 1.0,
        'centimeter': 10.0,
        'meter': 1000.0,
        'inch': 25.4,
        'foot': 304.8,
    }.get(unit, 1.0)


def _parse_transform(s: str | None) -> np.ndarray:
    if not s:
        return np.eye(4, dtype=np.float64)
    vals = [float(x) for x in s.replace(',', ' ').split()]
    if len(vals) != 12:
        return np.eye(4, dtype=np.float64)
    a,b,c,d,e,f,g,h,i,j,k,l = vals
    M = np.array([[a,b,c,d],
                  [e,f,g,h],
                  [i,j,k,l],
                  [0,0,0,1]], dtype=np.float64)
    return M


def _apply_transform(V: np.ndarray, M: np.ndarray) -> np.ndarray:
    ones = np.ones((V.shape[0], 1), dtype=V.dtype)
    Vh = np.hstack((V, ones))
    return (Vh @ M.T)[:, :3]


def _gather_object_meshes(root: ET.Element):
    meshes, comps, base_vol_units3 = {}, {}, {}
    for obj in root.findall('.//ns:object', NAMESPACE):
        oid = obj.get('id')
        mesh = obj.find('ns:mesh', NAMESPACE)
        if mesh is not None:
            vs = mesh.find('ns:vertices', NAMESPACE)
            verts = []
            if vs is not None:
                for v in vs.findall('ns:vertex', NAMESPACE):
                    verts.append((float(v.get('x', '0')),
                                  float(v.get('y', '0')),
                                  float(v.get('z', '0'))))
            V = np.array(verts, dtype=np.float64) if verts else np.zeros((0,3), dtype=np.float64)
            ts = mesh.find('ns:triangles', NAMESPACE)
            tris = []
            if ts is not None:
                for t in ts.findall('ns:triangle', NAMESPACE):
                    tris.append((int(t.get('v1', '0')),
                                 int(t.get('v2', '0')),
                                 int(t.get('v3', '0'))))
            T = np.array(tris, dtype=np.int32) if tris else np.zeros((0,3), dtype=np.int32)
            meshes[oid] = (V, T)
            # Базовый объём в «модельных» единицах (без unit)
            base_vol_units3[oid] = volume_tetra_units(V, T)
        else:
            comp_list = []
            comps_node = obj.find('ns:components', NAMESPACE)
            if comps_node is not None:
                for c in comps_node.findall('ns:component', NAMESPACE):
                    ref = c.get('objectid')
                    M = _parse_transform(c.get('transform'))
                    comp_list.append((ref, M))
            comps[oid] = comp_list
    return meshes, comps, base_vol_units3


def _flatten_object(oid: str, item_M: np.ndarray, meshes, comps, base_vol_units3) -> tuple[np.ndarray, np.ndarray, float]:
    """Вернуть (V, T, vol_units3_fast) — где vol_units3_fast складывается из базовых объёмов детей × |det(M3x3)|.
    V и T — трансформированные вершины и индексы (для точных расчётов).
    """
    if oid in meshes:
        V, T = meshes[oid]
        if V.size == 0 or T.size == 0:
            return np.zeros((0,3), dtype=np.float64), np.zeros((0,3), dtype=np.int32), 0.0
        Vt = _apply_transform(V, item_M)
        # быстрый объём: базовый объём * |det(M3x3)|
        det = abs(np.linalg.det(item_M[:3, :3]))
        vol_units3_fast = base_vol_units3.get(oid, 0.0) * det
        return Vt, T.copy(), vol_units3_fast

    # Составной объект
    out_V = []
    out_T = []
    offset = 0
    vol_units3_fast = 0.0
    for child_id, Mchild in comps.get(oid, []):
        Mcum = item_M @ Mchild
        Vc, Tc, vc = _flatten_object(child_id, Mcum, meshes, comps, base_vol_units3)
        if Vc.size == 0 or Tc.size == 0:
            vol_units3_fast += vc
            continue
        out_V.append(Vc)
        out_T.append(Tc + offset)
        offset += Vc.shape[0]
        vol_units3_fast += vc
    if out_V:
        V = np.vstack(out_V)
        T = np.vstack(out_T)
        return V, T, vol_units3_fast
    return np.zeros((0,3), dtype=np.float64), np.zeros((0,3), dtype=np.int32), vol_units3_fast


def parse_3mf(path: str):
    data = []
    with zipfile.ZipFile(path) as z:
        model_files = [f for f in z.namelist() if f.startswith('3D/') and f.endswith('.model')]
        for mf in model_files:
            root = ET.fromstring(z.read(mf))
            unit_scale = _unit_to_mm(root.get('unit'))
            meshes, comps, base_vol_units3 = _gather_object_meshes(root)
            build = root.find('ns:build', NAMESPACE)
            items = [] if build is None else build.findall('ns:item', NAMESPACE)
            if not items:
                for oid in meshes.keys() | comps.keys():
                    V, T, vol_units3_fast = _flatten_object(oid, np.eye(4), meshes, comps, base_vol_units3)
                    if V.size == 0 and vol_units3_fast == 0.0:
                        continue
                    V_mm = V * unit_scale
                    vol_cm3_fast = (vol_units3_fast * (unit_scale ** 3)) / 1000.0
                    name = f"{os.path.basename(mf)}:object_{oid}"
                    data.append((name, V_mm, T, vol_cm3_fast, {'type': '3mf', 'path': path}))
            else:
                for idx, item in enumerate(items, 1):
                    oid = item.get('objectid')
                    Mitem = _parse_transform(item.get('transform'))
                    V, T, vol_units3_fast = _flatten_object(oid, Mitem, meshes, comps, base_vol_units3)
                    if V.size == 0 and vol_units3_fast == 0.0:
                        continue
                    V_mm = V * unit_scale
                    vol_cm3_fast = (vol_units3_fast * (unit_scale ** 3)) / 1000.0
                    name = f"{os.path.basename(mf)}:item_{idx}"
                    data.append((name, V_mm, T, vol_cm3_fast, {'type': '3mf', 'path': path}))
    return data

# --------------------------
# STL ЧТЕНИЕ + ПОТОКОВЫЙ ОБЪЁМ
# --------------------------

def stl_stream_volume_cm3(path: str) -> float:
    """Потоковый объём STL в см³, читая бинарный STL напрямую (без построения меша)."""
    with open(path, 'rb') as f:
        f.seek(80)
        count = struct.unpack('<I', f.read(4))[0]
        total6 = 0.0
        for _ in range(count):
            f.read(12)  # нормаль
            v0 = struct.unpack('<fff', f.read(12))
            v1 = struct.unpack('<fff', f.read(12))
            v2 = struct.unpack('<fff', f.read(12))
            # вклад в 6*V
            cx = (v1[1]*v2[2] - v1[2]*v2[1])
            cy = (v1[2]*v2[0] - v1[0]*v2[2])
            cz = (v1[0]*v2[1] - v1[1]*v2[0])
            total6 += v0[0]*cx + v0[1]*cy + v0[2]*cz
            f.read(2)  # атрибуты
    vol_mm3 = abs(total6) / 6.0
    return vol_mm3 / 1000.0


def parse_stl(path: str):
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
    V = np.array(verts, dtype=np.float64)
    T = np.array(tris, dtype=np.int32)
    # Быстрый объём для STL по векторизованной сетке (альтернатива потоковому)
    vol_fast_cm3 = volume_tetra(V, T)
    return [("STL model", V, T, vol_fast_cm3, {'type': 'stl', 'path': path})]

# --------------------------
# ОБЩИЙ РАЗБОР ФАЙЛА
# --------------------------

def parse_geometry(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.3mf':
        return parse_3mf(path)
    if ext == '.stl':
        return parse_stl(path)
    raise ValueError('Only .3mf and .stl supported')

# --------------------------
# ВЕКТОРИЗОВАННЫЕ ВЫЧИСЛЕНИЯ
# --------------------------

def volume_tetra_units(V: np.ndarray, T: np.ndarray) -> float:
    """Объём в кубических МОДЕЛЬНЫХ единицах (без unit-конверсии)."""
    if V.size == 0 or T.size == 0:
        return 0.0
    v0 = V[T[:,0]]; v1 = V[T[:,1]]; v2 = V[T[:,2]]
    cross = np.cross(v1, v2)
    vol6 = np.einsum('ij,ij->i', v0, cross)
    return abs(vol6.sum()) / 6.0


def volume_tetra(V: np.ndarray, T: np.ndarray) -> float:
    """Объём в см³. V в мм."""
    if V.size == 0 or T.size == 0:
        return 0.0
    v0 = V[T[:,0]]; v1 = V[T[:,1]]; v2 = V[T[:,2]]
    cross = np.cross(v1, v2)
    vol6 = np.einsum('ij,ij->i', v0, cross)
    vol_mm3 = abs(vol6.sum()) / 6.0
    return vol_mm3 / 1000.0


def surface_area_mesh(V: np.ndarray, T: np.ndarray) -> float:
    if V.size == 0 or T.size == 0:
        return 0.0
    v0 = V[T[:,0]]; v1 = V[T[:,1]]; v2 = V[T[:,2]]
    area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1).sum()
    return area / 100.0


def xy_area_bbox_from_V(V: np.ndarray) -> float:
    if V.size == 0:
        return 0.0
    mins = V.min(axis=0); maxs = V.max(axis=0)
    dx, dy = (maxs[0]-mins[0]), (maxs[1]-mins[1])
    return (dx * dy) / 100.0


def volume_bbox(V: np.ndarray) -> float:
    if V.size == 0:
        return 0.0
    mins = V.min(axis=0); maxs = V.max(axis=0)
    dx, dy, dz = (maxs - mins)
    return (dx * dy * dz) / 1000.0

# --------------------------
# ВИЗУАЛИЗАЦИЯ (как было)
# --------------------------

def visualize(V: np.ndarray, T: np.ndarray):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    mesh = [[V[i] for i in tri] for tri in T]
    ax.add_collection3d(Poly3DCollection(mesh, facecolor='skyblue', edgecolor='gray', alpha=0.5))
    mins = V.min(axis=0); maxs = V.max(axis=0)
    ax.set_xlim(mins[0], maxs[0]); ax.set_ylim(mins[1], maxs[1]); ax.set_zlim(mins[2], maxs[2])
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    plt.tight_layout(); plt.show()

# --------------------------
# UI-ОБВЯЗКА
# --------------------------

def recalc(*args):
    t0 = time.time()
    output.config(state='normal')
    output.delete('1.0', tk.END)
    if not loaded:
        output.insert(tk.END, 'Сначала загрузите модель.')
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

    mode_val = mode.get()  # 'bbox' или 'tetra'
    fast_only = fast_volume_var.get() == 1
    stream_stl = stream_stl_var.get() == 1

    lines = []
    for idx, (name, V, T, vol_fast_cm3, src) in enumerate(loaded, start=1):
        # Выбор объёма
        if fast_only:
            if src.get('type') == 'stl' and stream_stl and src.get('path'):
                try:
                    V_model = stl_stream_volume_cm3(src['path'])
                except Exception:
                    V_model = vol_fast_cm3  # fallback
            else:
                # 3MF быстрый путь по детерминанту (vol_fast_cm3 уже посчитан на стадии парсинга)
                V_model = vol_fast_cm3 if vol_fast_cm3 > 0 else (volume_bbox(V) if mode_val=='bbox' else volume_tetra(V,T))
        else:
            # Полный точный путь
            V_model = volume_bbox(V) if mode_val=='bbox' else volume_tetra(V, T)

        if fast_only:
            # Быстрый режим: без расчёта стенок/крышек — только заполнение
            V_total = V_model * (infill / 100.0)
        else:
            # Точный FDM-разбор
            shell_area = surface_area_mesh(V, T)  # см^2
            xy_area = xy_area_bbox_from_V(V)      # см^2
            V_shell = shell_area * wall_count * wall_width / 10.0
            V_top_bottom = xy_area * top_bottom_layers * layer_height / 10.0
            shell_total = V_shell + V_top_bottom
            if shell_total > V_model * 0.6:
                scale = (V_model * 0.6) / max(shell_total, 1e-12)
                V_shell *= scale; V_top_bottom *= scale
            V_infill = max(0.0, V_model - V_shell - V_top_bottom) * (infill / 100.0)
            V_total = V_shell + V_top_bottom + V_infill

        weight = V_total * density  # г
        cost = weight * price

        lines.append(f'Объект {idx}: {os.path.basename(name)}\n')
        lines.append(f'  Объём модели: {V_model:.2f} см³' + ('  [FAST]' if fast_only else '\n'))
        lines.append(f'  Вес: {weight:.2f} г\n')
        lines.append(f'  Стоимость: {cost:.2f} руб.\n')
        lines.append('')

    dt = time.time() - t0
    lines.append(f'Время расчёта: {dt:.4f} с')

    output.insert(tk.END, ''.join(lines))
    output.config(state='disabled')


def open_file():
    path = filedialog.askopenfilename(filetypes=[('3D Files','*.3mf *.stl')])
    if not path:
        return
    try:
        objs = parse_geometry(path)
    except Exception as e:
        messagebox.showerror('Ошибка', str(e))
        return
    loaded.clear(); loaded.extend(objs)
    recalc()


def show_model():
    if not loaded:
        messagebox.showwarning('Нет модели','Загрузите файл')
        return
    for _,V,T,_,_ in loaded:
        visualize(V,T)

# --------------------------
# GUI
# --------------------------
root = tk.Tk()
root.title('3D калькулятор (PETG, FDM)')
root.geometry('520x660')
frame = tk.Frame(root, bg='#f9f9f9', padx=20, pady=20)
frame.pack(fill='both', expand=True)

tk.Label(frame, text='3D Калькулятор (.3mf / .stl)', font=('Arial',20,'bold'), bg='#f9f9f9').pack(pady=(0,10))

mode = tk.StringVar(value='tetra')
tk.Radiobutton(frame, text='Ограничивающий параллелепипед', variable=mode, value='bbox', font=('Arial',14), bg='#f9f9f9', fg='#7A6EB0', command=lambda: recalc()).pack(anchor='w')
tk.Radiobutton(frame, text='Тетраэдры', variable=mode, value='tetra', font=('Arial',14), bg='#f9f9f9', fg='#7A6EB0', command=lambda: recalc()).pack(anchor='w')

# Быстрые режимы
fast_frame = tk.Frame(frame, bg='#f9f9f9'); fast_frame.pack(pady=(4,6), fill='x')
fast_volume_var = tk.IntVar(value=0)
stream_stl_var = tk.IntVar(value=0)
cb_fast = tk.Checkbutton(fast_frame, text='Быстрый объём (без стенок/крышек)', variable=fast_volume_var, bg='#f9f9f9', command=lambda: recalc())
cb_fast.pack(anchor='w')
cb_stream = tk.Checkbutton(fast_frame, text='Потоковый STL (объём напрямую из файла)', variable=stream_stl_var, bg='#f9f9f9', command=lambda: recalc())
cb_stream.pack(anchor='w')

# Материал и заполнение
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

output = scrolledtext.ScrolledText(frame, font=('Consolas',12), state='disabled', height=18)
output.pack(fill='both', expand=True, pady=5)

btn_show = tk.Button(frame, text='Показать 3D', font=('Arial',12,'bold'), bg='#7A6EB0', fg='white', command=show_model)
btn_show.pack(pady=5, fill='x')

root.mainloop()