"""Chart-/JS-Helfer für das Dashboard."""


def _tooltip_date_logic(dates_json: str, is_custom: bool = False) -> str:
    """Erzeugt die JS-Tooltip-Logik für Datum/Zeit."""
    if is_custom:
        return f"""
                    title: (items) => {{
                        if (items.length > 0) {{
                            const idx = items[0].dataIndex;
                            const dateStr = {dates_json}[idx] || '';
                            const label = items[0].label;

                            let dateLabel = '';
                            if (dateStr) {{
                                const date = new Date(dateStr + 'T00:00:00');
                                const dd = String(date.getDate()).padStart(2, '0');
                                const mm = String(date.getMonth() + 1).padStart(2, '0');
                                const yyyy = date.getFullYear();
                                dateLabel = `${{dd}}.${{mm}}.${{yyyy}}`;
                            }}

                            return `📅 Date: ${{dateLabel}}\\n⏰ Time: ${{label}}`;
                        }}
                        return '';
                    }},"""
    return f"""
                    title: (items) => {{
                        if (items.length > 0) {{
                            const idx = items[0].dataIndex;
                            const dateStr = {dates_json}[idx] || '';
                            const label = items[0].label;

                            let dateLabel = '';
                            if (dateStr) {{
                                const today = new Date();
                                const date = new Date(dateStr + 'T00:00:00');

                                const todayMidnight = new Date(
                                    today.getFullYear(), today.getMonth(), today.getDate()
                                );
                                const dateMidnight = new Date(
                                    date.getFullYear(), date.getMonth(), date.getDate()
                                );

                                const diffDays = Math.round(
                                    (todayMidnight - dateMidnight) / (1000 * 60 * 60 * 24)
                                );

                                if (diffDays === 0) {{
                                    dateLabel = 'today';
                                }} else if (diffDays === 1) {{
                                    dateLabel = 'yesterday';
                                }} else {{
                                    const dd = String(date.getDate()).padStart(2, '0');
                                    const mm = String(date.getMonth() + 1).padStart(2, '0');
                                    const yyyy = date.getFullYear();
                                    dateLabel = `${{dd}}.${{mm}}.${{yyyy}}`;
                                }}
                            }}

                            return `📅 Date: ${{dateLabel}}\\n⏰ Time: ${{label}}`;
                        }}
                        return '';
                    }},"""


def _tooltip_label_color() -> str:
    """Erzeugt die JS-Tooltip-Farb-Logik."""
    return """
                    labelColor: (context) => ({
                        borderColor: context.dataset.borderColor,
                        backgroundColor: context.dataset.borderColor
                    }),
                    labelPointStyle: () => ({
                        pointStyle: 'circle',
                        rotation: 0
                    }),"""


def _render_chart_script(
    *,
    chart_id: str,
    chart_var: str,
    labels_json: str,
    dates_json: str,
    temp_values_json: str,
    hum_values_json: str,
    limit_datasets: str,
    legend_datasets: str = "",
    legend_onclick: str = "",
    legend_filter: str = "!label.startsWith('Warning') && !label.startsWith('Critical')",
    is_custom: bool = False,
) -> str:
    """Gemeinsame Chart.js-Generierung für Device-Tiles und Device-Detail."""
    prefix = chart_var
    labels_var = f"{prefix}Labels"
    dates_var = f"{prefix}Dates"
    has_hum_var = f"{prefix}HasHumidity"
    datasets_var = f"{prefix}Datasets"
    scales_var = f"{prefix}Scales"

    onclick_block = ""
    if legend_onclick:
        onclick_block = f"""
                onClick: {legend_onclick},"""

    tooltip_title = _tooltip_date_logic(dates_var, is_custom=is_custom)

    return f"""
const {labels_var} = {labels_json};
const {dates_var} = {dates_json};
const {has_hum_var} = {hum_values_json}.length > 0;

const {datasets_var} = [
    {{
        label: 'Temperature',
        data: {temp_values_json},
        borderColor: '#fb923c',
        borderWidth: 1.5,
        pointRadius: 2,
        pointHoverRadius: 4,
        yAxisID: 'temperature',
        tension: 0.3
    }},{limit_datasets}{legend_datasets}
];

const {scales_var} = {{
    x: {{
        ticks: {{
            color: '#9ca3af',
            callback: (value) => {labels_var}[value]
        }}
    }},
    temperature: {{
        type: 'linear',
        position: 'left',
        ticks: {{
            color: '#fb923c',
            callback: (value) => {{
                const rounded = Math.round(value * 10) / 10;
                return rounded + ' °C';
            }}
        }}
    }}
}};

if ({has_hum_var}) {{
    {datasets_var}.push({{
        label: 'Relative Humidity',
        data: {hum_values_json},
        borderColor: '#38bdf8',
        borderWidth: 1.5,
        pointRadius: 2,
        pointHoverRadius: 4,
        yAxisID: 'humidity',
        tension: 0.3
    }});
    {scales_var}.humidity = {{
        type: 'linear',
        position: 'right',
        ticks: {{
            color: '#38bdf8',
            callback: (value) => {{
                const rounded = Math.round(value * 10) / 10;
                return rounded + ' %';
            }}
        }},
        grid: {{ drawOnChartArea: false }}
    }};
}}

new Chart(document.getElementById('{chart_id}'), {{
    type: 'line',
    data: {{
        labels: {labels_var},
        datasets: {datasets_var}
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
            legend: {{
                labels: {{
                    color: '#d1d5db',
                    usePointStyle: true,
                    pointStyle: 'line',
                    filter: (item) => {{
                        const label = item.text || '';
                        return {legend_filter};
                    }},
                }},{onclick_block}
            }},
            tooltip: {{
                usePointStyle: true,
                boxWidth: 6,
                boxHeight: 6,
                filter: (item) => {{
                    const label = item.dataset.label || '';
                    return !label.startsWith('Warning') && !label.startsWith('Critical');
                }},
                callbacks: {{
                    labelColor: (context) => ({{
                        borderColor: context.dataset.borderColor,
                        backgroundColor: context.dataset.borderColor
                    }}),
                    labelPointStyle: () => ({{
                        pointStyle: 'circle',
                        rotation: 0
                    }}),
                    {tooltip_title}
                    label: (context) => {{
                        const value = (Math.round(context.parsed.y * 10) / 10).toFixed(1);
                        if (context.dataset.label === 'Temperature') {{
                            return `Temperature: ${{value}} °C`;
                        }}
                        return `Rel. Humidity: ${{value}} %`;
                    }}
                }}
            }}
        }},
        scales: {scales_var}
    }}
}});
"""


def _render_device_script(device: dict) -> str:
    """Erzeugt das Chart.js-Skript für ein Gerät."""
    if device["type"] == "placeholder":
        return ""
    chart_var = device["chart_id"].replace("-", "_")
    limit_datasets = ""
    for label, value, color, axis in device.get("limit_lines", []):
        limit_datasets += f"""
            {{
                label: '{label}',
                data: {chart_var}Labels.map(() => {value}),
                borderColor: '{color}',
                borderDash: [2, 2],
                pointRadius: 0,
                borderWidth: 0.8,
                yAxisID: '{axis}',
            }},"""
    return _render_chart_script(
        chart_id=device["chart_id"],
        chart_var=chart_var,
        labels_json=device["labels_json"],
        dates_json=device["dates_json"],
        temp_values_json=device["temp_values_json"],
        hum_values_json=device["hum_values_json"],
        limit_datasets=limit_datasets,
    )
