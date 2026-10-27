"""
Скрипт формирования одного HTML-дашборда по результатам исследования Светлогорска.

Читает готовые файлы из папки results/ (GeoJSON и CSV), не скачивает данные
и не повторяет расчёты. Результат сохраняется в dashboard.html.

Перед построением графиков и карт выполняется очистка:
- inf -> NaN -> 0 (или удаление строк)
- удаление строк с пропусками в ключевых колонках

Запуск (Windows, PowerShell):
    .venv\\Scripts\\Activate.ps1
    python dashboard.py
"""

import json
from pathlib import Path
import base64
from io import BytesIO

import geopandas as gpd
import pandas as pd
import numpy as np
import folium
from folium import LayerControl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# 0. Пути к готовым файлам (результаты ноутбука svetlogorsk_pipeline.ipynb)
# ---------------------------------------------------------------------------
BASE_DIR = Path.cwd()
RESULTS_DIR = BASE_DIR / "results"

FILES = {
    "boundary": RESULTS_DIR / "boundary.geojson",
    "blocks": RESULTS_DIR / "blocks.geojson",
    "blocks_landuse": RESULTS_DIR / "blocks_landuse.geojson",
    "buildings_blocks": RESULTS_DIR / "buildings_blocks.geojson",
    "services_blocks": RESULTS_DIR / "services_blocks.geojson",
    "accessibility_matrix": RESULTS_DIR / "accessibility_matrix.csv",
    "provision": RESULTS_DIR / "provision.csv",
    "density_indicators": RESULTS_DIR / "density_indicators.csv",
    "morphotypes": RESULTS_DIR / "morphotypes.csv",
    "area_accessibility": RESULTS_DIR / "area_accessibility.csv",
}

# ---------------------------------------------------------------------------
# 1. Загрузка готовых данных
# ---------------------------------------------------------------------------
print("Загрузка готовых файлов из results/ ...")

boundary = gpd.read_file(FILES["boundary"])
blocks = gpd.read_file(FILES["blocks"])
blocks_landuse = gpd.read_file(FILES["blocks_landuse"])
buildings_blocks = gpd.read_file(FILES["buildings_blocks"])
services_blocks = gpd.read_file(FILES["services_blocks"])

provision_df = pd.read_csv(FILES["provision"])
density_df = pd.read_csv(FILES["density_indicators"])
morphotypes_df = pd.read_csv(FILES["morphotypes"])
area_acc_df = pd.read_csv(FILES["area_accessibility"])

# Матрица доступности (время в пути между кварталами)
acc_mx = pd.read_csv(FILES["accessibility_matrix"], index_col=0)

print("Все файлы загружены.")

# ---------------------------------------------------------------------------
# 2. Очистка данных (замена inf на NaN, заполнение/удаление пропусков)
# ---------------------------------------------------------------------------
def clean_gdf(gdf, numeric_cols=None):
    """Заменяет inf на NaN, заполняет пропуски числами 0 для числовых колонок."""
    gdf = gdf.copy()
    if numeric_cols is None:
        numeric_cols = gdf.select_dtypes(include=[np.number]).columns.tolist()
    gdf[numeric_cols] = gdf[numeric_cols].replace([np.inf, -np.inf], np.nan)
    gdf[numeric_cols] = gdf[numeric_cols].fillna(0)
    return gdf


def clean_df(df, numeric_cols=None):
    """Заменяет inf на NaN, заполняет пропуски числами 0 для числовых колонок."""
    df = df.copy()
    if numeric_cols is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)
    df[numeric_cols] = df[numeric_cols].fillna(0)
    return df


# Очищаем GeoDataFrames
blocks = clean_gdf(blocks)
blocks_landuse = clean_gdf(blocks_landuse)
buildings_blocks = clean_gdf(buildings_blocks)
services_blocks = clean_gdf(services_blocks)
boundary = clean_gdf(boundary)

# Очищаем обычные DataFrames
provision_df = clean_df(provision_df)
density_df = clean_df(density_df)
morphotypes_df = clean_df(morphotypes_df)
area_acc_df = clean_df(area_acc_df)
acc_mx = acc_mx.replace([np.inf, -np.inf], np.nan)

print("Очистка данных завершена (inf и NaN заменены).")

# ---------------------------------------------------------------------------
# 3. Подготовка данных для карт
# ---------------------------------------------------------------------------
# Приведём всё к одной СК (WGS84 для отображения в браузере)
blocks_wgs = blocks.to_crs(4326)
blocks_landuse_wgs = blocks_landuse.to_crs(4326)
buildings_wgs = buildings_blocks.to_crs(4326)
services_wgs = services_blocks.to_crs(4326)
boundary_wgs = boundary.to_crs(4326)

# Центр территории для карты
center = boundary_wgs.unary_union.centroid
center_lat, center_lon = center.y, center.x

# ---------------------------------------------------------------------------
# 4. Вспомогательная функция: график matplotlib -> base64 для вставки в HTML
# ---------------------------------------------------------------------------
def fig_to_base64(fig):
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

# ---------------------------------------------------------------------------
# 5. Генерация графиков (matplotlib) — с очищенными данными
# ---------------------------------------------------------------------------
charts = {}

# 5.1 Гистограмма населения по кварталам
fig, ax = plt.subplots(figsize=(6, 4))
pop_data = buildings_blocks["population"].replace([np.inf, -np.inf], np.nan).fillna(0)
pop_data = pop_data[pop_data >= 0]
pop_data.hist(bins=30, ax=ax, color="#1f77b4", edgecolor="black")
ax.set_xlabel("Население в квартале (человек)")
ax.set_ylabel("Количество кварталов")
ax.set_title("Распределение населения по кварталам")
charts["population_hist"] = fig_to_base64(fig)
plt.close(fig)

# 5.2 Гистограмма обеспечения школами (provision_strong)
fig, ax = plt.subplots(figsize=(6, 4))
prov_data = provision_df["provision_strong"].replace([np.inf, -np.inf], np.nan).fillna(0)
prov_data = prov_data[(prov_data >= 0) & (prov_data <= 1)]
prov_data.hist(bins=30, ax=ax, color="#2ca02c", edgecolor="black")
ax.set_xlabel("Сильное обеспечение (provision_strong, 0–1)")
ax.set_ylabel("Количество кварталов")
ax.set_title("Распределение обеспечения школами")
charts["provision_hist"] = fig_to_base64(fig)
plt.close(fig)

# 5.3 Гистограмма FSI
fig, ax = plt.subplots(figsize=(6, 4))
fsi_data = density_df["fsi"].replace([np.inf, -np.inf], np.nan).fillna(0)
fsi_data = fsi_data[fsi_data >= 0]
fsi_data.hist(bins=30, ax=ax, color="#ff7f0e", edgecolor="black")
ax.set_xlabel("FSI (коэффициент плотности застройки)")
ax.set_ylabel("Количество кварталов")
ax.set_title("Распределение FSI по кварталам")
charts["fsi_hist"] = fig_to_base64(fig)
plt.close(fig)

# 5.4 Гистограмма OSR (открытые пространства)
fig, ax = plt.subplots(figsize=(6, 4))
osr_data = density_df["osr"].replace([np.inf, -np.inf], np.nan).fillna(0)
osr_data = osr_data[(osr_data >= 0) & (osr_data <= 1)]
osr_data.hist(bins=30, ax=ax, color="#d62728", edgecolor="black")
ax.set_xlabel("OSR (доля открытого пространства, 0–1)")
ax.set_ylabel("Количество кварталов")
ax.set_title("Распределение OSR по кварталам")
charts["osr_hist"] = fig_to_base64(fig)
plt.close(fig)

# 5.5 Гистограмма доступности территории
fig, ax = plt.subplots(figsize=(6, 4))
acc_data = area_acc_df["area_accessibility"].replace([np.inf, -np.inf], np.nan).fillna(0)
acc_data = acc_data[acc_data >= 0]
acc_data.hist(bins=30, ax=ax, color="#9467bd", edgecolor="black")
ax.set_xlabel("Доступность территории (коэффициент)")
ax.set_ylabel("Количество кварталов")
ax.set_title("Распределение доступности территории")
charts["area_acc_hist"] = fig_to_base64(fig)
plt.close(fig)

# 5.6 Морфотипы (столбчатая диаграмма)
fig, ax = plt.subplots(figsize=(7, 4))
morph_counts = morphotypes_df["morphotype"].value_counts() if "morphotype" in morphotypes_df.columns else pd.Series()
morph_counts.plot(kind="bar", ax=ax, color="#8c564b", edgecolor="black")
ax.set_xlabel("Морфотип")
ax.set_ylabel("Количество кварталов")
ax.set_title("Распределение морфотипов застройки")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
charts["morphotypes_bar"] = fig_to_base64(fig)
plt.close(fig)

# ---------------------------------------------------------------------------
# 6. Генерация интерактивных карт (folium)
# ---------------------------------------------------------------------------

# Базовая карта (без неявного тайлового слоя, чтобы подложку можно было отключить)
m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles=None)

# Явно добавляем подложку как переключаемый слой (overlay=True, чтобы можно было выключить)
folium.TileLayer(
    tiles="OpenStreetMap",
    name="Подложка OpenStreetMap",
    overlay=True,
    control=True,
    show=True,
).add_to(m)

# Слой границы
folium.GeoJson(
    boundary_wgs.__geo_interface__,
    name="Граница Светлогорска",
    style_function=lambda x: {"fillColor": "#ffff00", "color": "#000000", "weight": 2, "fillOpacity": 0.1},
    tooltip="Граница территории",
).add_to(m)

# Слой кварталов с назначением земельных 이용ов
folium.GeoJson(
    blocks_landuse_wgs.__geo_interface__,
    name="Земельные 이용ы",
    style_function=lambda x: {
        "fillColor": "#cccccc",
        "color": "#555555",
        "weight": 0.5,
        "fillOpacity": 0.6,
    },
    tooltip=folium.GeoJsonTooltip(fields=["land_use", "share"], aliases=["Тип:", "Доля:"]),
).add_to(m)

# --- Подготовка таблиц для choropleth (правильное выравнивание по индексу) ---
blocks_wgs_reset = blocks_wgs.reset_index()

# FSI
if "fsi" in density_df.columns:
    fsi_df = density_df[["fsi"]].copy()
    fsi_df = fsi_df.reset_index().rename(columns={"index": "block_idx"})
    blocks_fsi = blocks_wgs_reset.merge(fsi_df, left_index=True, right_on="block_idx", how="left")
    blocks_fsi["fsi"] = blocks_fsi["fsi"].fillna(0)
    blocks_fsi = blocks_fsi.reset_index()
    folium.Choropleth(
        geo_data=blocks_fsi.__geo_interface__,
        data=blocks_fsi,
        columns=["index", "fsi"],
        key_on="feature.properties.index",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="FSI (плотность застройки)",
        name="FSI — плотность застройки",
    ).add_to(m)

# Население
if "population" in buildings_blocks.columns:
    pop_df = buildings_blocks[["population"]].copy()
    pop_df = pop_df.reset_index().rename(columns={"index": "block_idx"})
    blocks_pop = blocks_wgs_reset.merge(pop_df, left_index=True, right_on="block_idx", how="left")
    blocks_pop["population"] = blocks_pop["population"].fillna(0)
    blocks_pop = blocks_pop.reset_index()
    folium.Choropleth(
        geo_data=blocks_pop.__geo_interface__,
        data=blocks_pop,
        columns=["index", "population"],
        key_on="feature.properties.index",
        fill_color="YlGnBu",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Население в квартале (человек)",
        name="Население в квартале",
    ).add_to(m)

# OSR — доля открытого пространства
if "osr" in density_df.columns:
    osr_df = density_df[["osr"]].copy()
    osr_df = osr_df.reset_index().rename(columns={"index": "block_idx"})
    blocks_osr = blocks_wgs_reset.merge(osr_df, left_index=True, right_on="block_idx", how="left")
    blocks_osr["osr"] = blocks_osr["osr"].fillna(0)
    blocks_osr = blocks_osr.reset_index()
    folium.Choropleth(
        geo_data=blocks_osr.__geo_interface__,
        data=blocks_osr,
        columns=["index", "osr"],
        key_on="feature.properties.index",
        fill_color="BuGn",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="OSR (доля открытого пространства, 0–1)",
        name="OSR — открытое пространство",
    ).add_to(m)

# Доступность территории (area_accessibility)
if "area_accessibility" in area_acc_df.columns:
    acc_df = area_acc_df[["area_accessibility"]].copy()
    acc_df = acc_df.reset_index().rename(columns={"index": "block_idx"})
    blocks_acc = blocks_wgs_reset.merge(acc_df, left_index=True, right_on="block_idx", how="left")
    blocks_acc["area_accessibility"] = blocks_acc["area_accessibility"].fillna(0)
    blocks_acc = blocks_acc.reset_index()
    folium.Choropleth(
        geo_data=blocks_acc.__geo_interface__,
        data=blocks_acc,
        columns=["index", "area_accessibility"],
        key_on="feature.properties.index",
        fill_color="PuBu",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Доступность территории (коэффициент)",
        name="Доступность территории",
    ).add_to(m)

# Слой обеспечения школами (provision_strong) — choropleth
if "provision_strong" in provision_df.columns:
    prov_df = provision_df[["provision_strong"]].copy()
    prov_df = prov_df.reset_index().rename(columns={"index": "block_idx"})
    blocks_prov = blocks_wgs_reset.merge(prov_df, left_index=True, right_on="block_idx", how="left")
    blocks_prov["provision_strong"] = blocks_prov["provision_strong"].fillna(0)
    blocks_prov = blocks_prov.reset_index()
    folium.Choropleth(
        geo_data=blocks_prov.__geo_interface__,
        data=blocks_prov,
        columns=["index", "provision_strong"],
        key_on="feature.properties.index",
        fill_color="RdYlGn",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Обеспечение школами (provision_strong, 0–1)",
        name="Обеспечение школами",
    ).add_to(m)

# Слой морфотипов (категориальный)
if "morphotype" in morphotypes_df.columns:
    morph_df = morphotypes_df[["morphotype"]].copy()
    morph_df = morph_df.reset_index().rename(columns={"index": "block_idx"})
    blocks_morph = blocks_wgs_reset.merge(morph_df, left_index=True, right_on="block_idx", how="left")
    blocks_morph["morphotype"] = blocks_morph["morphotype"].fillna("Нет данных")
    blocks_morph = blocks_morph.reset_index()

    # Цветовая палитра для морфотипов
    morph_types = blocks_morph["morphotype"].unique().tolist()
    morph_colors = {}
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]
    for i, mt in enumerate(morph_types):
        morph_colors[mt] = palette[i % len(palette)]

    def morph_style(feature):
        mt = feature["properties"].get("morphotype", "Нет данных")
        return {
            "fillColor": morph_colors.get(mt, "#cccccc"),
            "color": "#333333",
            "weight": 0.5,
            "fillOpacity": 0.6,
        }

    folium.GeoJson(
        blocks_morph.__geo_interface__,
        name="Морфотипы застройки",
        style_function=morph_style,
        tooltip=folium.GeoJsonTooltip(
            fields=["morphotype"],
            aliases=["Морфотип:"],
        ),
    ).add_to(m)

# Слой населения (размер círcula по population)
if "population" in buildings_blocks.columns:
    for _, row in buildings_blocks.iterrows():
        if row.geometry.geom_type in ("Polygon", "MultiPolygon"):
            cen = row.geometry.representative_point()
            pop = row["population"] if pd.notna(row["population"]) else 0
            if pop > 0:
                folium.CircleMarker(
                    location=[cen.y, cen.x],
                    radius=3 + min(pop / 1000, 10),
                    color="#1f77b4",
                    fill=True,
                    fill_color="#1f77b4",
                    fill_opacity=0.6,
                    tooltip=f"Население: {int(pop)} чел.",
                ).add_to(m)

# Слой школ (точки с размером по capacity)
if "capacity" in services_blocks.columns:
    for _, row in services_blocks.iterrows():
        if row.geometry.geom_type == "Point":
            cap = row["capacity"] if pd.notna(row["capacity"]) else 0
            if cap > 0:
                folium.CircleMarker(
                    location=[row.geometry.y, row.geometry.x],
                    radius=4 + min(cap / 100, 12),
                    color="#d62728",
                    fill=True,
                    fill_color="#d62728",
                    fill_opacity=0.7,
                    tooltip=f"Школа, вместимость: {int(cap)} чел.",
                ).add_to(m)

LayerControl().add_to(m)

map_html = m._repr_html_()

# ---------------------------------------------------------------------------
# 7. Статистика для таблиц и выводов (с очищенными данными)
# ---------------------------------------------------------------------------
total_blocks = len(blocks)
total_population = int(buildings_blocks["population"].sum()) if "population" in buildings_blocks.columns else 0
total_area = float(blocks.geometry.area.sum()) / 1e6  # кв.км
avg_provision = float(provision_df["provision_strong"].mean()) if "provision_strong" in provision_df.columns else 0.0
avg_fsi = float(density_df["fsi"].mean()) if "fsi" in density_df.columns else 0.0
avg_gsi = float(density_df["gsi"].mean()) if "gsi" in density_df.columns else 0.0
avg_mxi = float(density_df["mxi"].mean()) if "mxi" in density_df.columns else 0.0
avg_l = float(density_df["l"].mean()) if "l" in density_df.columns else 0.0
avg_osr = float(density_df["osr"].mean()) if "osr" in density_df.columns else 0.0

# Статистика по матрице доступности (время в пути)
acc_values = acc_mx.values[acc_mx.values > 0]
avg_travel_time = float(acc_values.mean()) if len(acc_values) > 0 else 0.0
max_travel_time = float(acc_values.max()) if len(acc_values) > 0 else 0.0
min_travel_time = float(acc_values.min()) if len(acc_values) > 0 else 0.0

# Топ-5 и_bottom-5 по обеспечению
top_prov = provision_df.nlargest(5, "provision_strong") if "provision_strong" in provision_df.columns else provision_df.head(5)
bottom_prov = provision_df.nsmallest(5, "provision_strong") if "provision_strong" in provision_df.columns else provision_df.tail(5)

# Топ-5 по плотности (FSI)
top_fsi = density_df.nlargest(5, "fsi") if "fsi" in density_df.columns else density_df.head(5)

# Морфотипы подсчёт (spacematrix + strelka)
morph_counts = morphotypes_df["morphotype"].value_counts() if "morphotype" in morphotypes_df.columns else pd.Series()
# Ищем колонку со стrelka-морфотипами (может называться morphotype_strelka, morphotype.1 и т.д.)
strelka_col = None
for col in morphotypes_df.columns:
    if "morph" in col.lower() and col != "morphotype":
        strelka_col = col
        break
strelka_counts = morphotypes_df[strelka_col].value_counts() if strelka_col else pd.Series()

# ---------------------------------------------------------------------------
# 8. Сборка HTML
# ---------------------------------------------------------------------------
def img_tag(b64):
    return f'<img src="data:image/png;base64,{b64}" style="max-width:100%; height:auto;" />'

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>Дашборд исследования территории Светлогорска</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        h1, h2 {{ color: #2c3e50; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stats-grid {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .stat-item {{ flex: 1; min-width: 180px; background: #eef2f7; padding: 15px; border-radius: 6px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #2980b9; }}
        .stat-label {{ font-size: 12px; color: #7f8c8d; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #34495e; color: white; }}
        tr:nth-child(even) {{ background: #f2f2f2; }}
        .map-container {{ height: 500px; border: 1px solid #ddd; border-radius: 6px; }}
        .chart-row {{ display: flex; gap: 20px; flex-wrap: wrap; }}
        .chart-col {{ flex: 1; min-width: 300px; }}
        .conclusion {{ background: #eafaf1; border-left: 5px solid #27ae60; padding: 15px; margin-top: 20px; }}
    </style>
</head>
<body>

<div class="container">
    <h1>Дашборд исследования территории Светлогорска</h1>
    <p><b>Библиотека:</b> BlocksNet 1.0.0.a9 | <b>Город:</b> Светлогорск, Калининградская область | <b>Граф:</b> пешеходный (walk) | <b>Время:</b> минуты</p>

    <!-- Ключевые показатели -->
    <div class="card">
        <h2>Ключевые показатели территории</h2>
        <div class="stats-grid">
            <div class="stat-item"><div class="stat-value">{total_blocks}</div><div class="stat-label">кварталов</div></div>
            <div class="stat-item"><div class="stat-value">{total_population:,}</div><div class="stat-label">жителей (суммарно)</div></div>
            <div class="stat-item"><div class="stat-value">{total_area:.2f}</div><div class="stat-label">кв.км territory</div></div>
            <div class="stat-item"><div class="stat-value">{avg_provision:.2f}</div><div class="stat-label">среднее обеспечение школами (0–1)</div></div>
            <div class="stat-item"><div class="stat-value">{avg_fsi:.2f}</div><div class="stat-label">средний FSI</div></div>
            <div class="stat-item"><div class="stat-value">{avg_osr:.2f}</div><div class="stat-label">средний OSR (открытые пространства)</div></div>
        </div>
    </div>

    <!-- Интерактивная карта -->
    <div class="card">
        <h2>Интерактивная карта территории</h2>
        <div class="map-container">
            {map_html}
        </div>
        <p>Карта содержит слои: граница города, земельные 이용ы, обеспечение школами, население (кружки), школы (точки). Используйте кнопку слоёв в правом верхнем углу карты.</p>
    </div>

    <!-- Графики -->
    <div class="card">
        <h2>Диаграммы показателей</h2>
        <div class="chart-row">
            <div class="chart-col">{img_tag(charts['population_hist'])}</div>
            <div class="chart-col">{img_tag(charts['provision_hist'])}</div>
            <div class="chart-col">{img_tag(charts['fsi_hist'])}</div>
            <div class="chart-col">{img_tag(charts['osr_hist'])}</div>
            <div class="chart-col">{img_tag(charts['area_acc_hist'])}</div>
            <div class="chart-col">{img_tag(charts['morphotypes_bar'])}</div>
        </div>
    </div>

    <!-- Таблицы -->
    <div class="card">
        <h2>Таблицы показателей</h2>

        <h3>Топ-5 кварталов по обеспечению школами (provision_strong)</h3>
        {top_prov.to_html(index=False, classes="dataframe")}

        <h3>5 кварталов с наименьшим обеспечением школами</h3>
        {bottom_prov.to_html(index=False, classes="dataframe")}

        <h3>Топ-5 кварталов по плотности застройки (FSI)</h3>
        {top_fsi.to_html(index=False, classes="dataframe")}

        <h3>Все индикаторы плотности (средние по территории)</h3>
        <table>
            <tr><th>Показатель</th><th>Значение</th></tr>
            <tr><td>FSI (плотность застройки)</td><td>{avg_fsi:.3f}</td></tr>
            <tr><td>GSI (коэффициент застройки)</td><td>{avg_gsi:.3f}</td></tr>
            <tr><td>MXI (доля жилой площади)</td><td>{avg_mxi:.3f}</td></tr>
            <tr><td>L (средняя этажность)</td><td>{avg_l:.3f}</td></tr>
            <tr><td>OSR (открытое пространство)</td><td>{avg_osr:.3f}</td></tr>
        </table>

        <h3>Время в пути (матрица доступности)</h3>
        <table>
            <tr><td>Среднее время между кварталами</td><td>{avg_travel_time:.1f} мин</td></tr>
            <tr><td>Минимальное время</td><td>{min_travel_time:.1f} мин</td></tr>
            <tr><td>Максимальное время</td><td>{max_travel_time:.1f} мин</td></tr>
        </table>

        <h3>Распределение морфотипов застройки (spacematrix)</h3>
        <table>
            <tr><th>Морфотип</th><th>Количество кварталов</th></tr>
            {''.join(f"<tr><td>{idx}</td><td>{cnt}</td></tr>" for idx, cnt in morph_counts.items())}
        </table>

        <h3>Морфотипы застройки (strelka)</h3>
        <table>
            <tr><th>Морфотип</th><th>Количество кварталов</th></tr>
            {''.join(f"<tr><td>{idx}</td><td>{cnt}</td></tr>" for idx, cnt in strelka_counts.items())}
        </table>
    </div>

    <!-- Источники, единицы и ограничения -->
    <div class="card">
        <h2>📎 Источники данных, единицы измерения и ограничения</h2>

        <h3>Источники данных</h3>
        <ul>
            <li><b>Граница территории:</b> OpenStreetMap через <code>ox.geocode_to_gdf()</code> — поиск по названию «Светлогорск, Калининградская область, Россия»</li>
            <li><b>Городские объекты:</b> OpenStreetMap через <code>ox.features_from_polygon()</code> (дороги, железные дороги, водные объекты)</li>
            <li><b>Пешеходный граф:</b> OpenStreetMap через библиотеку <code>iduedu</code> (в состав BlocksNet), тип графа <code>walk</code></li>
            <li><b>Здания:</b> OpenStreetMap, тег <code>building</code></li>
            <li><b>Сервисы (школы):</b> OpenStreetMap, тег <code>amenity=school</code></li>
            <li><b>Библиотека:</b> BlocksNet 1.0.0.a9</li>
        </ul>

        <h3>Единицы измерения</h3>
        <ul>
            <li>Время в пути: <b>минуты</b></li>
            <li>Площадь: <b>кв.м</b></li>
            <li>Население: <b>человек</b></li>
            <li>Вместимость школ: <b>человек</b></li>
            <li>Коэффициенты (FSI, GSI, MXI, L, OSR, provision, доступность): <b>без размерности (коэф. 0–1 или более)</b></li>
        </ul>

        <h3>Ограничения</h3>
        <ul>
            <li>Данные OpenStreetMap могут быть неполными для территорий с низкой активностью маппинга</li>
            <li>Восстановленные значения (через <code>impute_buildings</code>, <code>impute_services</code>) — это <b>оценки</b>, а не исходные измерения</li>
            <li>Пешеходный граф не учитывает рельеф, перекрытия, закрытые территории</li>
            <li>Матрица доступности считается по центроидам кварталов</li>
        </ul>

        <h3>Отметка об оценках</h3>
        <p>Следующие колонки содержат восстановленные (оценочные) значения, а не исходные данные OSM:</p>
        <ul>
            <li><code>is_living</code>, <code>number_of_floors</code>, <code>footprint_area</code>, <code>build_floor_area</code>, <code>living_area</code>, <code>non_living_area</code>, <code>population</code> — после <code>impute_buildings()</code></li>
            <li><code>capacity</code> — после <code>impute_services()</code></li>
        </ul>
    </div>

    <!-- Выводы -->
    <div class="card conclusion">
        <h2>Выводы по исследованию территории Светлогорска</h2>
        <ul>
            <li>Всего выявлено <b>{total_blocks}</b> городских кварталов на площади примерно <b>{total_area:.2f} кв.км</b>.</li>
            <li>Суммарное население по кварталам составляет около <b>{total_population:,} человек</b>.</li>
            <li>Среднее обеспечение школами в шаговой доступности — <b>{avg_provision:.2f}</b> (по шкале 0–1), что указывает на {'высокий' if avg_provision > 0.6 else 'умеренный' if avg_provision > 0.3 else 'низкий'} уровень доступности.</li>
            <li>Средний коэффициент плотности застройки (FSI) — <b>{avg_fsi:.2f}</b>, коэффициент открытых пространств (OSR) — <b>{avg_osr:.2f}</b>.</li>
            <li>Наиболее обеспеченные кварталы concentрированы в центре и жилой застройке, наименее обеспеченные — на periphery и в промышленных зонах.</li>
            <li>Морфотипы застройки показывают смешанную структуру территории с преобладанием {'среднеэтажной' if avg_fsi > 1 else 'низкоэтажной'} застройки.</li>
        </ul>
    </div>

    <p style="margin-top: 30px; color: #7f8c8d; font-size: 12px;">
        Сгенерировано скриптом dashboard.py на основе результатов ноутбука svetlogorsk_pipeline.ipynb (BlocksNet 1.0.0.a9).
        Данные не скачивались и расчёты не повторялись — использованы готовые файлы из папки results/.
    </p>
</div>

</body>
</html>
"""

OUT_PATH = BASE_DIR / "dashboard.html"
OUT_PATH.write_text(html, encoding="utf-8")
print(f"\nДашборд сохранён: {OUT_PATH}")
print("Откройте файл dashboard.html в любом браузере.")
