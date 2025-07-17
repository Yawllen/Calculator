import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os, struct, xml.etree.ElementTree as ET, zipfile
import numpy as np

# Material densities (g/cm³) and [price per gram is ignored here]
MATERIALS = {
    "Sealant TPU93": (1.20, 3.75),
    "Fiberpart ABS G4": (1.04, 3.07),
    "Fiberpart TPU C5": (1.20, 5.6),
    "Fiberpart ABSPA G8": (1.10, 4.0),
    "Fiberpart TPU G30": (1.20, 4.0),
    "Enduse SBS": (1.04, 2.4),
    "Enduse ABS": (1.04, 2.4),
    "Enduse PETG": (1.27, 2.33),
    "Enduse PP": (0.90, 8.08),
    "Proto PLA": (1.24, 3.07),
    "ContiFiber CPA": (1.15, 200.0),
    "Sealant SEBS": (1.04, 5.2),
    "Sealant TPU": (1.20, 5.98),
    "Proto PVA": (1.19, 9.5),
    "Enduse-PA": (1.15, 3.0),
    "Enduse-TPU D70": (1.20, 3.99),
    "Fiberpart ABS G13": (1.04, 6.65),
    "Fiberpart PP G": (0.90, 3.3),
    "Fiberpart PP G30": (0.90, 3.31),
    "Enduse PC": (1.20, 0.0),
    "Fiberpart PA12 G12": (1.01, 7.24),
    "Metalcast-316L": (8.00, 16.0),
    "Fiberpart PC G20": (1.20, 2.6),
    "Fiberpart PA G30": (1.15, 7.9),
    "Enduse TPU D60": (1.20, 1.9),
    "Sealant TPU A90": (1.20, 2.6),
    "Sealant TPU A70": (1.20, 6.4),
    "Fiberpart PA CF30": (1.15, 10.4),
    "Другой материал": (1.00, 2.0),
}

def parse_stl(path):
    verts, tris, idx = [], [], {}
    with open(path, 'rb') as f:
        f.seek(80)
        count = struct.unpack('<I', f.read(4))[0]
        for _ in range(count):
            f.read(12)
            face = []
            for _ in range(3):
                xyz = struct.unpack('<fff', f.read(12))
                if xyz not in idx:
                    idx[xyz] = len(verts)
                    verts.append(xyz)
                face.append(idx[xyz])
            tris.append(tuple(face))
            f.read(2)
    return verts, tris

def parse_3mf(path):
    verts, tris = [], []
    with zipfile.ZipFile(path) as z:
        ns = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
        for name in z.namelist():
            if name.endswith('.model'):
                tree = ET.parse(z.open(name))
                root = tree.getroot()
                for mesh in root.findall('.//ns:mesh', ns):
                    vlist = mesh.find('ns:vertices', ns)
                    tlist = mesh.find('ns:triangles', ns)
                    if vlist:
                        for v in vlist.findall('ns:vertex', ns):
                            verts.append((float(v.attrib['x']), float(v.attrib['y']), float(v.attrib['z'])))
                    if tlist:
                        for t in tlist.findall('ns:triangle', ns):
                            tris.append((int(t.attrib['v1']), int(t.attrib['v2']), int(t.attrib['v3'])))
    return verts, tris

def volume_bbox(verts):
    xs, ys, zs = zip(*verts)
    return (max(xs)-min(xs))*(max(ys)-min(ys))*(max(zs)-min(zs))/1000.0

def volume_tetra(verts, tris):
    arr = np.array(verts)
    tot = 0
    for a,b,c in tris:
        tot += np.dot(arr[a], np.cross(arr[b], arr[c]))/6.0
    return abs(tot)/1000.0

class ModelCalc(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("3D Калькулятор (.3mf / .stl)")
        self.geometry("500x650")
        self.configure(bg='#f9f9f9')
        self._build_ui()
        self.mainloop()

    def _build_ui(self):
        frame = tk.Frame(self, bg='#f9f9f9', padx=20, pady=20)
        frame.pack(fill='both', expand=True)

        tk.Label(frame, text='3D Калькулятор (.3mf / .stl)',
                 font=('Arial',20,'bold'), bg='#f9f9f9').pack(pady=(0,10))

        self.mode = tk.StringVar(value='bbox')
        tk.Radiobutton(frame, text='Ограничивающий\nпараллелепипед', variable=self.mode, value='bbox',
                       font=('Arial',14), bg='#f9f9f9', fg='#7A6EB0',
                       selectcolor='#f9f9f9').pack(anchor='w')
        tk.Radiobutton(frame, text='Тетраэдры', variable=self.mode, value='tetra',
                       font=('Arial',14), bg='#f9f9f9', fg='#7A6EB0',
                       selectcolor='#f9f9f9').pack(anchor='w')

        mat_frame = tk.Frame(frame, bg='#f9f9f9')
        mat_frame.pack(pady=(5,10), fill='x')
        tk.Label(mat_frame, text='Материал:', font=('Arial',12), bg='#f9f9f9').pack(side='left')
        self.material = tk.StringVar(value=list(MATERIALS.keys())[0])
        tk.OptionMenu(mat_frame, self.material, *MATERIALS.keys()).pack(side='left', padx=5)

        infill_frame = tk.Frame(frame, bg='#f9f9f9')
        infill_frame.pack(pady=(5,10), fill='x')
        tk.Label(infill_frame, text='Заполнение (%):', font=('Arial',12), bg='#f9f9f9').pack(side='left')
        self.entry_infill = tk.Entry(infill_frame, width=6, font=('Arial',12))
        self.entry_infill.insert(0,'35')
        self.entry_infill.pack(side='left', padx=5)

        btn_load = tk.Button(frame, text='Загрузить 3D файл', font=('Arial',12,'bold'),
                             bg='#7A6EB0', fg='white', command=self.open_file)
        btn_load.pack(pady=10, fill='x')

        self.output = scrolledtext.ScrolledText(frame, font=('Consolas',12), state='disabled')
        self.output.pack(fill='both', expand=True, pady=5)

        btn_calc = tk.Button(frame, text='Рассчитать', font=('Arial',12,'bold'),
                             bg='#7A6EB0', fg='white', command=self.recalc)
        btn_calc.pack(pady=5, fill='x')

        btn_back = tk.Button(frame, text='← Назад', font=('Arial',10),
                             bg='#CCCCCC', fg='black', command=self.back)
        btn_back.pack(side='bottom', pady=10)

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('3D Files','*.3mf *.stl')])
        if not path: return
        try:
            if path.lower().endswith('.stl'):
                self.verts, self.tris = parse_stl(path)
            else:
                self.verts, self.tris = parse_3mf(path)
        except Exception as e:
            messagebox.showerror('Ошибка', str(e))
            return

    def recalc(self):
        self.output.config(state='normal')
        self.output.delete('1.0', tk.END)
        try:
            infill = float(self.entry_infill.get())
        except ValueError:
            messagebox.showerror('Ошибка','Введите корректный % заполнения')
            self.output.config(state='disabled')
            return
        eff = min(infill+15,100)/100.0
        dens, price = MATERIALS[self.material.get()]
        mode = self.mode.get()
        verts = getattr(self, 'verts', None)
        tris = getattr(self, 'tris', None)
        if not verts:
            self.output.insert(tk.END, 'Сначала загрузите файл\n')
            self.output.config(state='disabled')
            return
        vol = volume_bbox(verts) if mode=='bbox' else volume_tetra(verts, tris)
        weight = vol * dens * eff
        cost = weight * price
        self.output.insert(tk.END, f'Объём: {vol:.2f} см³\n')
        self.output.insert(tk.END, f'Вес: {weight:.2f} г\n')
        self.output.insert(tk.END, f'Стоимость: {cost:.2f} руб.\n')
        self.output.config(state='disabled')

    def back(self):
        from main import MainMenu
        self.destroy()
        MainMenu()

if __name__=='__main__':
    ModelCalc()
