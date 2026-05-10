from __future__ import annotations

import heapq
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

import config
from src.events import ARRIVAL, SERVICE_END, PEAK_START, PEAK_END, CLOSE
from src.logger import setup_logger
from src.simulator import KojoSimulator


SCENARIOS = {
    "two_employees": False,
    "extra_employee_peak": True,
}


class KojoVisualApp:
    """
    Interfaz visual para observar una réplica de Kojo's Kitchen evento por evento.
    Ejecuta una nueva réplica usando KojoSimulator y procesa los eventos
    uno por uno con un delay configurable.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Kojo's Kitchen - Pixel Event Simulator")
        self.root.geometry("1250x780")
        self.root.minsize(1100, 700)

        self.logger = setup_logger(
            enabled=False,
            level="INFO",
            log_file=config.LOG_FILE,
        )

        self.simulator: Optional[KojoSimulator] = None
        self.running = False
        self.after_id = None

        self.current_event_text = "Sin evento"
        self.last_event_info = {
            "event_type": None,
            "client_id": None,
            "employee_id": None,
        }

        self.build_layout()
        self.reset_simulation()

    def build_layout(self) -> None:
        self.build_controls()
        self.build_status_panel()
        self.build_canvas_panel()
        self.build_event_log()

    def build_controls(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Controles")
        frame.pack(fill="x", padx=10, pady=8)

        ttk.Label(frame, text="Escenario:").grid(row=0, column=0, padx=5, pady=5)

        self.scenario_var = tk.StringVar(value="extra_employee_peak")
        scenario_box = ttk.Combobox(
            frame,
            textvariable=self.scenario_var,
            values=list(SCENARIOS.keys()),
            state="readonly",
            width=24,
        )
        scenario_box.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Configuración:").grid(row=0, column=2, padx=5, pady=5)

        self.config_ids = [
            experiment_config["config_id"]
            for experiment_config in config.EXPERIMENT_CONFIGS
        ]

        self.config_var = tk.StringVar(value=self.config_ids[0])
        config_box = ttk.Combobox(
            frame,
            textvariable=self.config_var,
            values=self.config_ids,
            state="readonly",
            width=30,
        )
        config_box.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame, text="Seed:").grid(row=0, column=4, padx=5, pady=5)

        self.seed_var = tk.StringVar(value=str(config.DEFAULT_SEED))
        ttk.Entry(frame, textvariable=self.seed_var, width=8).grid(
            row=0,
            column=5,
            padx=5,
            pady=5,
        )

        ttk.Label(frame, text="Delay ms:").grid(row=0, column=6, padx=5, pady=5)

        self.delay_var = tk.StringVar(value="400")
        ttk.Entry(frame, textvariable=self.delay_var, width=8).grid(
            row=0,
            column=7,
            padx=5,
            pady=5,
        )

        ttk.Button(frame, text="Iniciar", command=self.start).grid(
            row=0,
            column=8,
            padx=5,
            pady=5,
        )

        ttk.Button(frame, text="Pausar", command=self.pause).grid(
            row=0,
            column=9,
            padx=5,
            pady=5,
        )

        ttk.Button(frame, text="Paso", command=self.step_once).grid(
            row=0,
            column=10,
            padx=5,
            pady=5,
        )

        ttk.Button(frame, text="Reiniciar", command=self.reset_simulation).grid(
            row=0,
            column=11,
            padx=5,
            pady=5,
        )

    def build_status_panel(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Estado")
        frame.pack(fill="x", padx=10, pady=5)

        self.clock_label = ttk.Label(frame, text="Reloj: -", width=35)
        self.clock_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.event_label = ttk.Label(frame, text="Evento: -", width=120)
        self.event_label.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        self.metrics_label = ttk.Label(frame, text="Métricas: -", width=160)
        self.metrics_label.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=10,
            pady=5,
            sticky="w",
        )

    def build_canvas_panel(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Vista visual del restaurante")
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(
            frame,
            bg="#f4e8c1",
            height=430,
            highlightthickness=0,
        )
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)

    def build_event_log(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Eventos procesados")
        frame.pack(fill="both", expand=True, padx=10, pady=8)

        self.event_log = tk.Text(
            frame,
            height=9,
            font=("Consolas", 9),
            wrap="none",
        )
        self.event_log.pack(fill="both", expand=True, padx=5, pady=5)

    def reset_simulation(self) -> None:
        self.pause()

        try:
            seed = int(self.seed_var.get())
        except ValueError:
            messagebox.showerror("Error", "La semilla debe ser un número entero.")
            return

        scenario_name = self.scenario_var.get()
        use_extra_employee = SCENARIOS[scenario_name]
        experiment_config = self.get_selected_experiment_config()

        self.simulator = KojoSimulator(
            seed=seed,
            use_extra_employee=use_extra_employee,
            logger=self.logger,
            experiment_config=experiment_config,
        )

        self.simulator.schedule_initial_events()

        self.current_event_text = "Simulación reiniciada"
        self.last_event_info = {
            "event_type": None,
            "client_id": None,
            "employee_id": None,
        }

        self.clear_event_log()
        self.log_visual(
            f"Simulación creada | escenario={scenario_name} | "
            f"config={experiment_config['config_id']} | seed={seed}"
        )
        self.log_visual(f"Clientes generados: {self.simulator.generated_customers}")
        self.log_visual("Presiona Iniciar para correr o Paso para avanzar evento por evento.")

        self.update_display()

    def start(self) -> None:
        if self.simulator is None:
            self.reset_simulation()

        if self.running:
            return

        self.running = True
        self.schedule_next_step()

    def pause(self) -> None:
        self.running = False

        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def schedule_next_step(self) -> None:
        if not self.running:
            return

        self.step_once()

        if self.running:
            delay = self.get_delay_ms()
            self.after_id = self.root.after(delay, self.schedule_next_step)

    def step_once(self) -> None:
        if self.simulator is None:
            return

        if not self.simulator.event_queue:
            self.finish_simulation()
            return

        event = heapq.heappop(self.simulator.event_queue)

        self.last_event_info = self.extract_event_info(event)
        event_description = self.describe_event(event)

        self.simulator.advance_clock(event.time)
        self.process_event(event)

        self.current_event_text = event_description
        self.log_visual(event_description)
        self.update_display()

        if not self.simulator.event_queue:
            self.finish_simulation()

    def finish_simulation(self) -> None:
        self.pause()

        if self.simulator is None:
            return

        try:
            self.simulator.validate_end_state()
            results = self.simulator.build_results()

            self.current_event_text = "Simulación finalizada"
            self.log_visual("SIMULACIÓN FINALIZADA")
            self.log_visual(
                "Resultados | "
                f"total={results['total_customers']} | "
                f"completed={results['completed_customers']} | "
                f"delayed={results['delayed_customers']} | "
                f"delayed_percentage={results['delayed_percentage']:.2f}% | "
                f"average_wait={results['average_wait']:.2f} | "
                f"max_wait={results['max_wait']:.2f}"
            )

            self.update_display()

        except RuntimeError as error:
            messagebox.showerror("Error de simulación", str(error))
            self.log_visual(f"ERROR: {error}")

    def process_event(self, event) -> None:
        if self.simulator is None:
            return

        if event.event_type == ARRIVAL:
            self.simulator.handle_arrival(event.payload)

        elif event.event_type == SERVICE_END:
            self.simulator.handle_service_end(event.payload)

        elif event.event_type == PEAK_START:
            self.simulator.handle_peak_start()

        elif event.event_type == PEAK_END:
            self.simulator.handle_peak_end()

        elif event.event_type == CLOSE:
            self.simulator.handle_close()

        else:
            raise RuntimeError(f"Evento no reconocido: {event.event_type}")

    def extract_event_info(self, event) -> dict:
        info = {
            "event_type": event.event_type,
            "client_id": None,
            "employee_id": None,
        }

        if event.event_type == ARRIVAL:
            client = event.payload
            info["client_id"] = client.id

        elif event.event_type == SERVICE_END:
            employee = event.payload
            info["employee_id"] = employee.id

            if employee.current_client is not None:
                info["client_id"] = employee.current_client.id

        return info

    def describe_event(self, event) -> str:
        time_text = self.format_time(event.time)

        if event.event_type == ARRIVAL:
            client = event.payload
            return (
                f"t={event.time:.2f} ({time_text}) | LLEGADA | "
                f"cliente={client.id} | producto={client.product} | "
                f"servicio={client.service_time:.2f}"
            )

        if event.event_type == SERVICE_END:
            employee = event.payload
            client = employee.current_client

            if client is None:
                return (
                    f"t={event.time:.2f} ({time_text}) | FIN SERVICIO | "
                    f"empleado={employee.id}"
                )

            return (
                f"t={event.time:.2f} ({time_text}) | FIN SERVICIO | "
                f"cliente={client.id} | empleado={employee.id}"
            )

        if event.event_type == PEAK_START:
            return f"t={event.time:.2f} ({time_text}) | INICIO HORA PICO"

        if event.event_type == PEAK_END:
            return f"t={event.time:.2f} ({time_text}) | FIN HORA PICO"

        if event.event_type == CLOSE:
            return f"t={event.time:.2f} ({time_text}) | CIERRE DEL LOCAL"

        return f"t={event.time:.2f} ({time_text}) | {event.event_type}"

    def update_display(self) -> None:
        if self.simulator is None:
            return

        clock = self.simulator.clock

        self.clock_label.config(
            text=f"Reloj: t={clock:.2f} min | {self.format_time(clock)}"
        )

        self.event_label.config(
            text=f"Evento actual: {self.current_event_text}"
        )

        delayed_percentage = 0.0
        average_wait = 0.0

        if self.simulator.total_customers > 0:
            delayed_percentage = (
                100.0
                * self.simulator.delayed_customers
                / self.simulator.total_customers
            )
            average_wait = (
                self.simulator.total_waiting_time
                / self.simulator.total_customers
            )

        self.metrics_label.config(
            text=(
                f"Llegados={self.simulator.total_customers} | "
                f"Atendidos={self.simulator.completed_customers} | "
                f"En cola={len(self.simulator.waiting_queue)} | "
                f"Demorados={self.simulator.delayed_customers} | "
                f"% espera > 5={delayed_percentage:.2f}% | "
                f"Espera prom={average_wait:.2f} | "
                f"Espera máx={self.simulator.max_waiting_time:.2f}"
            )
        )

        self.draw_scene()

    def draw_scene(self) -> None:
        if self.simulator is None:
            return

        self.canvas.delete("all")

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width < 100:
            width = 1100

        if height < 100:
            height = 430

        self.draw_background(width, height)
        self.draw_timeline(width)
        self.draw_entrance()
        self.draw_queue()
        self.draw_service_area()
        self.draw_event_banner(width)
        self.draw_legend(width, height)

    def draw_background(self, width: int, height: int) -> None:
        """
        Fondo tipo juego retro con piso cuadriculado.
        """

        self.canvas.create_rectangle(
            0,
            0,
            width,
            height,
            fill="#f4e8c1",
            outline="",
        )

        tile = 24

        for row in range(3, int(height // tile) + 1):
            for col in range(int(width // tile) + 1):
                x1 = col * tile
                y1 = row * tile
                x2 = x1 + tile
                y2 = y1 + tile

                color = "#f8edc9" if (row + col) % 2 == 0 else "#efe0b5"

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=color,
                    outline="#e5d39c",
                )

        self.canvas.create_rectangle(
            20,
            45,
            width - 20,
            height - 20,
            fill="",
            outline="#8b6f47",
            width=4,
        )

        self.canvas.create_text(
            width // 2,
            25,
            text="Kojo's Kitchen - Pixel UI",
            font=("Arial", 16, "bold"),
            fill="#5a3512",
        )

        self.canvas.create_rectangle(
            40,
            70,
            width - 40,
            height - 45,
            fill="",
            outline="#d2b48c",
            width=2,
        )

    def draw_timeline(self, width: int) -> None:
        if self.simulator is None:
            return

        x0 = 80
        x1 = width - 80
        y = 395

        self.canvas.create_line(x0, y, x1, y, fill="#777777", width=3)

        day_length = config.DAY_CLOSE - config.DAY_OPEN
        current_ratio = min(max(self.simulator.clock / day_length, 0.0), 1.0)
        current_x = x0 + (x1 - x0) * current_ratio

        self.canvas.create_line(x0, y, current_x, y, fill="#2f80ed", width=5)
        self.canvas.create_oval(
            current_x - 7,
            y - 7,
            current_x + 7,
            y + 7,
            fill="#2f80ed",
            outline="#174d8c",
        )

        marks = [
            (0, "10:00"),
            (90, "11:30"),
            (210, "1:30"),
            (420, "5:00"),
            (540, "7:00"),
            (660, "9:00"),
        ]

        for minute, label in marks:
            ratio = minute / day_length
            x = x0 + (x1 - x0) * ratio

            self.canvas.create_line(x, y - 8, x, y + 8, fill="#444444", width=2)
            self.canvas.create_text(x, y + 22, text=label, font=("Arial", 9))

        for start, end in config.PEAK_PERIODS:
            start_x = x0 + (x1 - x0) * (start / day_length)
            end_x = x0 + (x1 - x0) * (end / day_length)

            self.canvas.create_rectangle(
                start_x,
                y - 18,
                end_x,
                y - 11,
                fill="#ffbf69",
                outline="",
            )

        self.canvas.create_text(
            x0,
            y - 28,
            text="Línea del día",
            anchor="w",
            font=("Arial", 9, "bold"),
            fill="#444444",
        )

    def draw_entrance(self) -> None:
        self.canvas.create_rectangle(
            45,
            155,
            115,
            265,
            fill="#d8f3dc",
            outline="#40916c",
            width=3,
        )

        self.canvas.create_text(
            80,
            140,
            text="Entrada",
            font=("Arial", 12, "bold"),
            fill="#1b4332",
        )

        self.canvas.create_text(
            80,
            210,
            text="IN",
            font=("Arial", 18, "bold"),
            fill="#1b4332",
        )

        self.canvas.create_line(
            120,
            210,
            170,
            210,
            arrow=tk.LAST,
            fill="#777777",
            width=3,
        )

    def draw_queue(self) -> None:
        if self.simulator is None:
            return

        queue = list(self.simulator.waiting_queue)
        max_visible = 12

        self.canvas.create_text(
            290,
            95,
            text=f"Cola FIFO ({len(queue)} clientes)",
            font=("Arial", 13, "bold"),
            fill="#3b3b3b",
        )

        self.canvas.create_rectangle(
            160,
            115,
            540,
            315,
            fill="#f7fbff",
            outline="#90caf9",
            width=2,
        )

        positions = [
            (205, 170),
            (265, 170),
            (325, 170),
            (385, 170),
            (445, 170),
            (505, 170),
            (205, 255),
            (265, 255),
            (325, 255),
            (385, 255),
            (445, 255),
            (505, 255),
        ]

        for x, y in positions:
            self.canvas.create_rectangle(
                x - 24,
                y - 28,
                x + 24,
                y + 28,
                fill="#ffffff",
                outline="#d0d0d0",
                dash=(2, 2),
            )

        visible_queue = queue[:max_visible]

        for position, client in enumerate(visible_queue):
            x, y = positions[position]
            waiting_so_far = max(0.0, self.simulator.clock - client.arrival_time)

            fill = "#ffdd99" if waiting_so_far <= config.WAIT_THRESHOLD else "#ff8fab"
            outline = "#d97706" if waiting_so_far <= config.WAIT_THRESHOLD else "#c9184a"

            is_last_event = (
                self.last_event_info["event_type"] == ARRIVAL
                and self.last_event_info["client_id"] == client.id
            )

            if is_last_event:
                outline = "#2f80ed"

            self.draw_customer_icon(
                x=x,
                y=y,
                label=f"C{client.id}",
                fill=fill,
                outline=outline,
                scale=1.0,
            )

            self.canvas.create_text(
                x,
                y + 38,
                text=f"{waiting_so_far:.1f} min",
                font=("Arial", 8),
                fill="#333333",
            )

        if len(queue) > max_visible:
            self.canvas.create_text(
                350,
                305,
                text=f"+ {len(queue) - max_visible} clientes más en cola",
                font=("Arial", 11, "bold"),
                fill="#c9184a",
            )

        self.canvas.create_line(
            545,
            210,
            625,
            210,
            arrow=tk.LAST,
            fill="#777777",
            width=3,
        )

    def draw_service_area(self) -> None:
        if self.simulator is None:
            return

        self.canvas.create_text(
            810,
            95,
            text="Estaciones de servicio",
            font=("Arial", 13, "bold"),
            fill="#3b3b3b",
        )

        employees_by_id = {
            employee.id: employee
            for employee in self.simulator.employees
        }

        station_positions = {
            1: (650, 120),
            2: (650, 225),
            3: (650, 330),
        }

        for employee_id, (x, y) in station_positions.items():
            employee = employees_by_id.get(employee_id)
            self.draw_employee_station(employee_id, employee, x, y)

    def draw_employee_station(self, employee_id: int, employee, x: int, y: int) -> None:
        station_width = 410
        station_height = 80

        if employee is None:
            bg = "#eeeeee"
            border = "#bbbbbb"
            status = "NO EXISTE"
        elif not employee.active:
            bg = "#eeeeee"
            border = "#999999"
            status = "INACTIVO"
        elif employee.busy:
            if employee.is_extra and not employee.can_take_new_clients:
                bg = "#fff0b3"
                border = "#d69e2e"
                status = "OCUPADO - se retira al terminar"
            else:
                bg = "#ffd6d6"
                border = "#d62828"
                status = "OCUPADO"
        else:
            bg = "#d8f3dc"
            border = "#40916c"
            status = "LIBRE"

        self.canvas.create_rectangle(
            x,
            y,
            x + station_width,
            y + station_height,
            fill=bg,
            outline=border,
            width=3,
        )

        self.canvas.create_rectangle(
            x + 120,
            y + 15,
            x + 390,
            y + 65,
            fill="#c2a477",
            outline="#7f5539",
            width=2,
        )

        self.canvas.create_text(
            x + 15,
            y + 15,
            text=f"E{employee_id}",
            anchor="nw",
            font=("Arial", 14, "bold"),
            fill="#222222",
        )

        self.draw_worker_icon(
            x=x + 80,
            y=y + 42,
            active=employee is not None and employee.active,
            busy=employee is not None and employee.busy,
        )

        extra_text = ""

        if employee is not None and employee.is_extra:
            extra_text = " | extra"

        self.canvas.create_text(
            x + 155,
            y + 28,
            text=f"Empleado {employee_id}{extra_text}",
            anchor="w",
            font=("Arial", 11, "bold"),
            fill="#222222",
        )

        self.canvas.create_text(
            x + 155,
            y + 50,
            text=f"Estado: {status}",
            anchor="w",
            font=("Arial", 10),
            fill="#222222",
        )

        if employee is not None and employee.current_client is not None:
            client = employee.current_client

            is_last_event = (
                self.last_event_info["client_id"] == client.id
                or self.last_event_info["employee_id"] == employee.id
            )

            outline = "#2f80ed" if is_last_event else "#6a040f"

            self.draw_customer_icon(
                x=x + 345,
                y=y + 40,
                label=f"C{client.id}",
                fill="#ffb703",
                outline=outline,
                scale=0.9,
            )

            self.canvas.create_text(
                x + 345,
                y + 72,
                text=client.product,
                font=("Arial", 8, "bold"),
                fill="#222222",
            )

    def draw_event_banner(self, width: int) -> None:
        event_type = self.last_event_info.get("event_type")

        if event_type == ARRIVAL:
            fill = "#dbeafe"
            outline = "#2f80ed"
        elif event_type == SERVICE_END:
            fill = "#dcfce7"
            outline = "#16a34a"
        elif event_type in [PEAK_START, PEAK_END]:
            fill = "#ffedd5"
            outline = "#ea580c"
        elif event_type == CLOSE:
            fill = "#e5e7eb"
            outline = "#374151"
        else:
            fill = "#f8fafc"
            outline = "#94a3b8"

        self.canvas.create_rectangle(
            580,
            55,
            width - 55,
            85,
            fill=fill,
            outline=outline,
            width=2,
        )

        self.canvas.create_text(
            595,
            70,
            text=self.current_event_text,
            anchor="w",
            font=("Arial", 10, "bold"),
            fill="#222222",
        )

    def draw_legend(self, width: int, height: int) -> None:
        x = width - 310
        y = height - 100

        self.canvas.create_rectangle(
            x,
            y,
            x + 270,
            y + 72,
            fill="#ffffff",
            outline="#cccccc",
        )

        self.canvas.create_text(
            x + 10,
            y + 10,
            text="Leyenda",
            anchor="nw",
            font=("Arial", 9, "bold"),
        )

        items = [
            ("#d8f3dc", "Empleado libre"),
            ("#ffd6d6", "Empleado ocupado"),
            ("#ff8fab", "Cliente espera > 5 min"),
            ("#ffbf69", "Franja de hora pico"),
        ]

        for idx, (color, label) in enumerate(items):
            yy = y + 28 + idx * 12
            self.canvas.create_rectangle(
                x + 10,
                yy,
                x + 22,
                yy + 8,
                fill=color,
                outline="#555555",
            )
            self.canvas.create_text(
                x + 30,
                yy + 4,
                text=label,
                anchor="w",
                font=("Arial", 8),
            )

    def draw_pixel_sprite(
        self,
        x: int,
        y: int,
        sprite: list[str],
        palette: dict[str, str],
        pixel_size: int = 4,
    ) -> None:

        if not sprite:
            return

        rows = len(sprite)
        cols = max(len(row) for row in sprite)

        start_x = x - (cols * pixel_size) // 2
        start_y = y - (rows * pixel_size) // 2

        for row_index, row in enumerate(sprite):
            for col_index, cell in enumerate(row):
                if cell == ".":
                    continue

                color = palette.get(cell)

                if color is None:
                    continue

                x1 = start_x + col_index * pixel_size
                y1 = start_y + row_index * pixel_size
                x2 = x1 + pixel_size
                y2 = y1 + pixel_size

                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=color,
                    outline=color,
                )

    def draw_customer_icon(
        self,
        x: float,
        y: float,
        label: str,
        fill: str,
        outline: str,
        scale: float = 1.0,
    ) -> None:

        pixel = max(2, int(4 * scale))

        customer_sprite = [
            "........",
            "..hhhh..",
            ".hssssh.",
            ".hssssh.",
            "..s..s..",
            ".cccccc.",
            ".c.c..c.",
            ".cccccc.",
            "...pp...",
            "..p..p..",
            ".p....p.",
            "........",
        ]

        palette = {
            "h": "#5a3d2b",   # cabello
            "s": "#f2c6a0",   # piel
            "c": fill,        # camisa
            "p": "#3d5a80",   # pantalón
        }

        self.canvas.create_oval(
            x - 14 * scale,
            y + 20 * scale,
            x + 14 * scale,
            y + 28 * scale,
            fill="#c8b895",
            outline="",
        )

        self.draw_pixel_sprite(
            x=int(x),
            y=int(y),
            sprite=customer_sprite,
            palette=palette,
            pixel_size=pixel,
        )

        self.canvas.create_rectangle(
            x - 18 * scale,
            y - 26 * scale,
            x + 18 * scale,
            y + 24 * scale,
            outline=outline,
            width=2,
        )

        self.canvas.create_text(
            x,
            y - 34 * scale,
            text=label,
            font=("Arial", max(7, int(8 * scale)), "bold"),
            fill="#222222",
        )

    def draw_worker_icon(
        self,
        x: float,
        y: float,
        active: bool,
        busy: bool,
    ) -> None:

        if not active:
            uniform_color = "#9e9e9e"
        elif busy:
            uniform_color = "#e76f51"
        else:
            uniform_color = "#52b788"

        chef_sprite = [
            "..wwww..",
            ".wwwwww.",
            "..wwww..",
            "..ssss..",
            ".ssssss.",
            "..s..s..",
            "..uuuu..",
            ".uuuuuu.",
            ".uu..uu.",
            "...pp...",
            "..p..p..",
            ".p....p.",
        ]

        palette = {
            "w": "#ffffff",       # gorro
            "s": "#f2c6a0",       # piel
            "u": uniform_color,   # uniforme
            "p": "#6c757d",       # pantalón
        }

        self.canvas.create_oval(
            x - 16,
            y + 24,
            x + 16,
            y + 32,
            fill="#c8b895",
            outline="",
        )

        self.draw_pixel_sprite(
            x=int(x),
            y=int(y),
            sprite=chef_sprite,
            palette=palette,
            pixel_size=4,
        )

        self.canvas.create_text(
            x,
            y + 38,
            text="CHEF",
            font=("Arial", 8, "bold"),
            fill="#333333",
        )

    def get_selected_experiment_config(self) -> dict:
        selected_id = self.config_var.get()

        for experiment_config in config.EXPERIMENT_CONFIGS:
            if experiment_config["config_id"] == selected_id:
                return experiment_config

        return config.EXPERIMENT_CONFIGS[0]

    def get_delay_ms(self) -> int:
        try:
            delay = int(self.delay_var.get())
        except ValueError:
            delay = 400

        return max(1, delay)

    def log_visual(self, message: str) -> None:
        self.event_log.insert(tk.END, message + "\n")
        self.event_log.see(tk.END)

    def clear_event_log(self) -> None:
        self.event_log.delete("1.0", tk.END)

    def format_time(self, minutes_since_open: float) -> str:

        total_minutes = int(round(10 * 60 + minutes_since_open))
        hour_24 = (total_minutes // 60) % 24
        minute = total_minutes % 60

        suffix = "a.m." if hour_24 < 12 else "p.m."

        hour_12 = hour_24 % 12

        if hour_12 == 0:
            hour_12 = 12

        return f"{hour_12}:{minute:02d} {suffix}"


def main() -> None:
    config.validate_config()

    root = tk.Tk()
    KojoVisualApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()