from textual.app import App
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Vertical
from rich.table import Table
from rich.console import Group
from rich.text import Text
from rich import box
import psutil
import time
import subprocess
import re

class SystemStats(Static):
    def on_mount(self) -> None:
        """组件挂载时启动更新循环"""
        self.set_interval(1, self.update_stats)

    def update_stats(self) -> None:
        """更新系统统计信息"""
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        
        stats = f"""[bold blue]CPU 使用率:[/] {cpu_percent}%
[bold green]内存使用:[/] {memory.percent}%
总内存: {memory.total / (1024**3):.1f}GB
已用内存: {memory.used / (1024**3):.1f}GB
可用内存: {memory.available / (1024**3):.1f}GB"""
        
        self.update(stats)

class NPUStats(Static):
    def on_mount(self) -> None:
        """组件挂载时启动更新循环"""
        self.set_interval(1, self.update_stats)

    def get_gradient_color(self, percentage):
        """根据百分比返回渐变颜色
        0-60%: 绿色到黄色
        60-100%: 黄色到红色
        """
        if percentage <= 60:
            # 从绿色渐变到黄色
            ratio = percentage / 60
            return f"rgb({int(255*ratio)},255,0)"
        else:
            # 从黄色渐变到红色
            ratio = (percentage - 60) / 40
            return f"rgb(255,{int(255*(1-ratio))},0)"

    def create_progress_bar(self, percentage):
        """创建带颜色的进度条"""
        bar_width = 20
        filled = int(percentage / 5)  # 每5%一个方块
        
        bar = Text()
        # 添加填充的方块
        for i in range(filled):
            bar.append("█", style=self.get_gradient_color(percentage))
        # 添加未填充的方块
        bar.append("░" * (bar_width - filled), style="white")
        # 添加百分比数值
        bar.append(f" {percentage:.1f}%", style=self.get_gradient_color(percentage))
        
        return bar


    def parse_npu_info(self, output):
        """解析npu-smi info的输出"""
        # 基础信息正则表达式
        pattern = r'\| (\d+)\s+(\w+)\s+\| (\w+)\s+\| ([\d.]+)\s+([\d]+)\s+.*?\n\| \d+\s+\| ([^\s]+)\s+\| (\d+)\s+[^/]+/ \d+\s+(\d+)\s*/\s*(\d+)'
        # 进程信息正则表达式 - 更新以匹配"No running processes"的情况
        process_pattern = r'\| (\d+)\s+0\s+\| (\d+)\s+\| ([^\s|]+)\s+\| (\d+)'
        no_process_pattern = r'No running processes found in NPU (\d+)'
        
        parts = output.split("+---------------------------+---------------+----------------------------------------------------+")
        
        npu_info = []
        process_info = []
        
        # 解析设备信息
        matches = re.finditer(pattern, parts[1])
        for match in matches:
            npu_id = match.group(1)
            name = match.group(2)
            health = match.group(3)
            power = match.group(4)
            temp = match.group(5)
            bus_id = match.group(6)
            aicore = match.group(7)
            hbm_used = int(match.group(8))
            hbm_total = int(match.group(9))
            
            hbm_percent = (hbm_used / hbm_total) * 100 if hbm_total > 0 else 0
            
            npu_info.append({
                'id': npu_id,
                'name': name,
                'health': health,
                'power': power,
                'temp': temp,
                'bus_id': bus_id,
                'aicore': int(aicore),
                'hbm_used': hbm_used,
                'hbm_total': hbm_total,
                'hbm_percent': hbm_percent,
            })
        
        # 解析进程信息
        if len(parts) > 2:
            # 首先检查是否有运行的进程
            process_section = parts[2]
            
            # 检查每个NPU的进程状态
            for npu in npu_info:
                npu_id = npu['id']
                # 查找是否有"No running processes"的匹配
                no_process_match = re.search(f'No running processes found in NPU {npu_id}', process_section)
                
                if no_process_match:
                    # 添加一个空进程信息
                    process_info.append({
                        'npu_id': npu_id,
                        'pid': '-',
                        'name': 'No Process',
                        'memory': 0,
                        'total_memory': npu['hbm_total']
                    })
                else:
                    # 查找正在运行的进程
                    for proc_match in re.finditer(process_pattern, process_section):
                        if proc_match.group(1) == npu_id:
                            process_info.append({
                                'npu_id': npu_id,
                                'pid': proc_match.group(2),
                                'name': proc_match.group(3),
                                'memory': int(proc_match.group(4)),
                                'total_memory': npu['hbm_total']
                            })
        
        return npu_info, process_info

    def update_stats(self) -> None:
        """更新NPU统计信息"""
        # 创建NPU基础信息表格
        npu_table = Table(
            title="[bold white]NPU 设备信息[/]",  # 设置标题样式
            box=box.HEAVY,
            padding=(0, 1),
            show_header=True,
            header_style="bold white",  # 修改表头颜色
            border_style="grey70",      # 使用更柔和的灰色作为边框颜色
            show_lines=True,
            title_style="bold white",   # 设置标题样式
            style="grey89"              # 设置表格整体文字颜色
        )
        
        # 设置列
        npu_table.add_column("NPU ID", justify="center")
        npu_table.add_column("名称", justify="center")
        npu_table.add_column("温度", justify="center")
        npu_table.add_column("功耗(W)", justify="center")
        npu_table.add_column("HBM使用率", justify="left", min_width=35)
        npu_table.add_column("AI Core", justify="left", min_width=35)
        npu_table.add_column("状态", justify="center")
        
        # 创建进程信息表格，使用相同的样式
        proc_table = Table(
            title="[bold white]NPU 进程信息[/]",  # 设置标题样式
            box=box.HEAVY,
            padding=(0, 1),
            show_header=True,
            header_style="bold white",  # 修改表头颜色
            border_style="grey70",      # 使用相同的边框颜色
            show_lines=True,
            title_style="bold white",   # 设置标题样式
            style="grey89"              # 设置表格整体文字颜色
        )
        
        # 设置列
        proc_table.add_column("NPU ID", justify="center")
        proc_table.add_column("PID", justify="center")
        proc_table.add_column("进程名", justify="left", min_width=40)
        proc_table.add_column("内存使用", justify="right", min_width=35)
        
        try:
            result = subprocess.run(['npu-smi', 'info'], 
                                capture_output=True, 
                                text=True)
            
            if result.returncode == 0:
                npu_info, process_info = self.parse_npu_info(result.stdout)
                
                # 填充NPU信息表格
                for npu in npu_info:
                    npu_table.add_row(
                        npu['id'],
                        f"{npu['name']}",
                        f"[yellow]{npu['temp']}°C[/]",  # 添加温度颜色
                        f"[blue]{npu['power']}[/]",     # 添加功耗颜色
                        self.create_progress_bar(npu['hbm_percent']),
                        self.create_progress_bar(float(npu['aicore'])),
                        f"[green]OK[/green]" if npu['health'] == "OK" else f"[red]{npu['health']}[/red]"
                    )
                
                # 填充进程信息表格
                if process_info:  # 如果有进程信息
                    for proc in process_info:
                        memory_text = f"{proc['memory']} / {proc['total_memory']} MB" if proc['pid'] != '-' else "-"
                        proc_table.add_row(
                            proc['npu_id'],
                            f"[cyan]{proc['pid']}[/]" if proc['pid'] != '-' else "-",  # 添加PID颜色
                            f"[grey]{proc['name']}[/]" if proc['pid'] == '-' else f"[white]{proc['name']}[/]",
                            f"[blue]{memory_text}[/]" if proc['pid'] != '-' else "-"   # 添加内存使用颜色
                        )
                else:  # 如果没有进程信息，添加一个提示行
                    proc_table.add_row(
                        "-",
                        "-",
                        "[grey]No running processes[/grey]",
                        "-"
                    )
                
                # 添加表格分隔
                separator = Text("\n", style="white")
                
                # 使用Group组合两个表格，中间添加空行分隔
                self.update(Group(npu_table, separator, proc_table))
            
        except FileNotFoundError:
            npu_table.add_row("Error", "npu-smi command not found", "", "", "", "", "")
            self.update(npu_table)
        except Exception as e:
            npu_table.add_row("Error", str(e), "", "", "", "", "")
            self.update(npu_table)

class SystemMonitorApp(App):
    """系统监控TUI应用"""
    
    BINDINGS = [("q", "quit", "退出")]
    
    def compose(self):
        """创建UI布局"""
        yield Header(show_clock=True)
        yield Container(
            Vertical(
                SystemStats(),
                NPUStats(),
                id="stats-container"
            )
        )
        yield Footer()

    def on_mount(self):
        """设置样式"""
        self.screen.styles.background = "black"

def main():
    app = SystemMonitorApp()
    app.run()
