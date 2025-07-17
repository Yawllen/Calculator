
import tkinter as tk
from tkinter import messagebox

def calculate():
    try:
        dx = float(entry_dx.get())
        dy = float(entry_dy.get())
        dz = float(entry_dz.get())
        rate = float(entry_rate.get())
    except ValueError:
        messagebox.showerror("Ошибка", "Введите корректные числовые значения")
        return

    volume_cm3 = (dx * dy * dz) / 1000.0
    cost = volume_cm3 * rate

    result_label.config(text=f"Объём: {volume_cm3:.2f} см³\nСтоимость: {cost:.2f} руб.")

root = tk.Tk()
root.title("Ручной расчёт 3D стоимости")
root.geometry("400x400")
root.configure(bg='#f9f9f9')

frame = tk.Frame(root, padx=20, pady=20, bg='#f9f9f9')
frame.pack(expand=True, fill='both')

tk.Label(frame, text="Введите габариты в мм:", font=('Arial', 14), bg='#f9f9f9').pack(pady=(0, 10))

tk.Label(frame, text="Длина (DX)", font=('Arial', 12), bg='#f9f9f9').pack(anchor='w')
entry_dx = tk.Entry(frame, font=('Arial', 12))
entry_dx.pack(fill='x', pady=2)

tk.Label(frame, text="Ширина (DY)", font=('Arial', 12), bg='#f9f9f9').pack(anchor='w')
entry_dy = tk.Entry(frame, font=('Arial', 12))
entry_dy.pack(fill='x', pady=2)

tk.Label(frame, text="Высота (DZ)", font=('Arial', 12), bg='#f9f9f9').pack(anchor='w')
entry_dz = tk.Entry(frame, font=('Arial', 12))
entry_dz.pack(fill='x', pady=2)

tk.Label(frame, text="Цена (руб/см³):", font=('Arial', 12), bg='#f9f9f9').pack(anchor='w', pady=(10, 0))
entry_rate = tk.Entry(frame, font=('Arial', 12))
entry_rate.pack(fill='x', pady=5)
entry_rate.insert(0, "3.5")

btn = tk.Button(frame, text="Рассчитать", font=('Arial', 12, 'bold'), bg='#7A6EB0', fg='white', command=calculate)
btn.pack(pady=10, fill='x')

result_label = tk.Label(frame, text="Результат появится здесь", font=('Arial', 12), bg='#f9f9f9', justify="left")
result_label.pack(pady=(10, 0))

root.mainloop()
