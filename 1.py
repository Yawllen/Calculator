import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os, struct, zipfile, xml.etree.ElementTree as ET
import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Global
loaded = []
NAMESPACE = {'ns': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}

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

wall_count = 2
wall_width = 0.4
layer_height = 0.2
top_bottom_layers = 4
VOLUME_FLOW_RATE_MM3_SEC = 13

# ... все ранее определенные функции и recalc без изменений ...

# GUI и переменные
root = tk.Tk()
root.title('3D калькулятор (PETG, FDM)')
root.geometry('500x600')

frame = tk.Frame(root, bg='#f9f9f9', padx=20, pady=20)
frame.pack(fill='both', expand=True)

tk.Label(frame, text='3D Калькулятор (.3mf / .stl)', font=('Arial',20,'bold'), bg='#f9f9f9').pack(pady=(0,10))

selected_material = tk.StringVar(value='Enduse PETG')
entry_infill = tk.Entry(frame, font=('Arial', 12))
entry_infill.insert(0, '10')

output = scrolledtext.ScrolledText(frame, font=('Consolas', 12), state='disabled')
output.pack(fill='both', expand=True, pady=5)

root.mainloop()
