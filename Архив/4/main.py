import tkinter as tk
from manual_calc import ManualCalc
from model_calc import ModelCalc

class MainMenu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('3D Калькулятор — Меню')
        self.geometry('400x200')
        self.configure(bg='#f9f9f9')
        self._build_ui()

    def _build_ui(self):
        frame = tk.Frame(self, bg='#f9f9f9', pady=20)
        frame.pack(expand=True, fill='both')

        btn_manual = tk.Button(frame, text='Ручной ввод размера',
                               font=('Arial',12,'bold'),
                               bg='#7A6EB0', fg='white',
                               width=25, command=self.open_manual)
        btn_model  = tk.Button(frame, text='Расчет по модели',
                               font=('Arial',12,'bold'),
                               bg='#7A6EB0', fg='white',
                               width=25, command=self.open_model)

        btn_manual.pack(pady=10)
        btn_model.pack(pady=10)

    def open_manual(self):
        self.destroy()
        ManualCalc()

    def open_model(self):
        self.destroy()
        ModelCalc()

if __name__=='__main__':
    MainMenu().mainloop()
