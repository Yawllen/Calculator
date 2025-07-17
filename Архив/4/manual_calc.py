import tkinter as tk
from tkinter import messagebox
class ManualCalc(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ручной расчет 3D стоимости")
        self.geometry("400x450")
        self.configure(bg='#f9f9f9')
        self._build_ui()
        self.mainloop()

    def _build_ui(self):
        frame = tk.Frame(self, padx=20, pady=20, bg='#f9f9f9')
        frame.pack(expand=True, fill='both')

        tk.Label(frame, text="Ручной ввод размеров", font=('Arial',16,'bold'), bg='#f9f9f9').pack(pady=(0,10))
        tk.Label(frame, text="Длина (мм):", font=('Arial',12), bg='#f9f9f9').pack(anchor='w')
        self.entry_dx = tk.Entry(frame, font=('Arial',12))
        self.entry_dx.pack(fill='x', pady=5)

        tk.Label(frame, text="Ширина (мм):", font=('Arial',12), bg='#f9f9f9').pack(anchor='w')
        self.entry_dy = tk.Entry(frame, font=('Arial',12))
        self.entry_dy.pack(fill='x', pady=5)

        tk.Label(frame, text="Высота (мм):", font=('Arial',12), bg='#f9f9f9').pack(anchor='w')
        self.entry_dz = tk.Entry(frame, font=('Arial',12))
        self.entry_dz.pack(fill='x', pady=5)

        tk.Label(frame, text="Цена (руб/см³):", font=('Arial',12), bg='#f9f9f9').pack(anchor='w', pady=(10,0))
        self.entry_rate = tk.Entry(frame, font=('Arial',12))
        self.entry_rate.pack(fill='x', pady=5)
        self.entry_rate.insert(0, "3.5")

        btn_calc = tk.Button(frame, text="Рассчитать", font=('Arial',12,'bold'),
                             bg='#7A6EB0', fg='white', command=self.calculate)
        btn_calc.pack(pady=10, fill='x')

        self.result_label = tk.Label(frame, text="Результат появится здесь",
                                     font=('Arial',12), bg='#f9f9f9', justify="left")
        self.result_label.pack(pady=(10,0))

        btn_back = tk.Button(frame, text="← Назад", font=('Arial',10),
                             bg='#CCCCCC', fg='black', command=self.back)
        btn_back.pack(side='bottom', pady=10)

    def calculate(self):
        try:
            dx = float(self.entry_dx.get())
            dy = float(self.entry_dy.get())
            dz = float(self.entry_dz.get())
            rate = float(self.entry_rate.get())
        except ValueError:
            messagebox.showerror("Ошибка","Введите корректные числа")
            return
        vol = dx*dy*dz/1000.0
        cost = vol * rate
        self.result_label.config(text=f"Объем: {vol:.2f} см³\nСтоимость: {cost:.2f} руб.")

    def back(self):
        from main import MainMenu
        self.destroy()
        MainMenu()
