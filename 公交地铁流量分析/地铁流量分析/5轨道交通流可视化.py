import geopandas
import numpy as np
import pandas as pd
from shapely.geometry import LineString
import matplotlib.pyplot as plt
import transbigdata as tbd
import matplotlib
import os
import warnings

# 忽略警告
warnings.filterwarnings("ignore")

# 设置 Matplotlib 显示中文和负号
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['font.serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 设置 transbigdata 底图瓦片存储路径
imgsavepath = 'map_tiles/'
if not os.path.exists(imgsavepath):
    os.makedirs(imgsavepath)  # 创建目录
tbd.set_imgsavepath(imgsavepath)

# 可选：设置 Mapbox Token（若使用 Mapbox 底图）
# tbd.set_mapboxtoken('your_mapbox_token')  # 替换为你的 Mapbox Access Token

# 读取轨道站点数据
stop = pd.read_csv(r'data/stop.csv')
metro_passenger = pd.read_csv(r'data/metro_passenger.csv')

# 为站点生成 geometry 列，存储地理信息
stop['geometry'] = geopandas.points_from_xy(stop['lon'], stop['lat'])
stop = geopandas.GeoDataFrame(stop, crs="EPSG:4326")  # 设置初始CRS

# 获取地铁线路名称
stop['line'] = stop['linename'].apply(lambda r: r.split('(')[0])

# 更改地铁5号线支线的名称
stop.loc[stop['line'] == '地铁5号线支线', 'line'] = '地铁5号线'

# 产生各线路的站点编号
stop['ID'] = stop.groupby(['linename']).cumcount() + 1

# 为地铁4号线环线补充两个站点
r3_inner = stop[stop['linename'] == '地铁4号线(内圈(宜山路-宜山路))'].iloc[0].copy()
r3_inner['ID'] = stop[stop['linename'] == '地铁4号线(内圈(宜山路-宜山路))']['ID'].max() + 1
r3_outer = stop[stop['linename'] == '地铁4号线(外圈(宜山路-宜山路))'].iloc[0].copy()
r3_outer['ID'] = stop[stop['linename'] == '地铁4号线(外圈(宜山路-宜山路))']['ID'].max() + 1
stop = pd.concat([stop, pd.DataFrame([r3_inner, r3_outer])], ignore_index=True)

# 按线路和ID排序
stop = stop.sort_values(by=['linename', 'ID'])

# 读取轨道线路GIS文件
line = geopandas.read_file('data/line.json', encoding='utf-8')
line = line.to_crs("EPSG:4326")  # 转换为目标CRS


# 定义生成轨道段的函数
def getline(r2, line_geometry):
    ls = []
    if r2['o_project'] < r2['d_project']:
        tmp1 = np.linspace(r2['o_project'], r2['d_project'], 10)
    else:
        tmp1 = np.linspace(r2['o_project'] - line_geometry.length, r2['d_project'], 10)
    tmp1[tmp1 < 0] = tmp1[tmp1 < 0] + line_geometry.length
    for j in tmp1:
        ls.append(line_geometry.interpolate(j))
    return LineString(ls)


# 用轨道站点对轨道线进行切分并生成断面信息
lss = []
for k in range(len(line)):
    r = line.iloc[k]
    line_geometry = r['geometry']
    tmp = stop[stop['linename'] == r['linename']].copy()

    # 避免 SettingWithCopyWarning，使用 .loc
    for i in tmp.columns:
        tmp[i + '1'] = tmp[i].shift(-1)
    tmp = tmp.iloc[:-1]
    tmp = tmp[['stationnames', 'stationnames1', 'geometry', 'geometry1', 'linename']]

    tmp['o_project'] = tmp['geometry'].apply(lambda r1: line_geometry.project(r1))
    tmp['d_project'] = tmp['geometry1'].apply(lambda r1: line_geometry.project(r1))
    tmp['geometry'] = tmp.apply(lambda r2: getline(r2, line_geometry), axis=1)
    lss.append(tmp)

metro_line_splited = pd.concat(lss)
metro_line_splited = geopandas.GeoDataFrame(metro_line_splited, geometry='geometry')  # 不直接设置CRS，继承现有CRS
metro_line_splited = metro_line_splited.set_crs("EPSG:4326", allow_override=True)  # 覆盖CRS

# 提取线路名并处理
metro_line_splited['line'] = metro_line_splited['linename'].apply(lambda r: r.split('(')[0].lstrip('地铁'))
metro_line_splited.loc[metro_line_splited['line'] == '5号线支线', 'line'] = '5号线'

# 补齐起终点站点名称
metro_line_splited['o'] = metro_line_splited['line'] + metro_line_splited['stationnames']
metro_line_splited['d'] = metro_line_splited['line'] + metro_line_splited['stationnames1']

# 保留必要的列，包括 o_project 用于绘图
metro_line_splited = metro_line_splited[['o', 'd', 'geometry', 'o_project', 'd_project', 'linename']]

# 存储分割的轨道断面线型
metro_line_splited.to_file(r'data/metro_line_splited.json', driver='GeoJSON', encoding='utf-8')

# 连接客流数据
metro_line_toplot = pd.merge(metro_line_splited, metro_passenger, on=['o', 'd'])
metro_line_toplot['linewidth'] = metro_line_toplot['count'] / metro_line_toplot['count'].max()

# 对轨道断面按客流大小分10组
groupnum = 10
metro_line_toplot = metro_line_toplot.sort_values(by='count')
metro_line_toplot['linewidth'] = (np.arange(len(metro_line_toplot)) * groupnum / len(metro_line_toplot)).astype(
    int) / groupnum + 0.1

# 平移轨道线
metro_line_parallel = metro_line_toplot.copy()
rate = 0.004
metro_line_parallel['geometry'] = metro_line_parallel.apply(
    lambda r: r['geometry'].parallel_offset(rate * r['linewidth']), axis=1)

# 扩样25倍
metro_line_parallel['count'] *= 25

# 删除空的geometry
metro_line_parallel = metro_line_parallel[~metro_line_parallel['geometry'].is_empty]
# 设置图片保存路径
imgfolder = '图片/'
if not os.path.exists(imgfolder):
    os.makedirs(imgfolder)  # 创建图片文件夹

# 绘制三张图

# 图1：初步轨道断面图
fig1 = plt.figure(figsize=(10, 8))
ax1 = fig1.add_subplot(111)
lss[0].plot(ax=ax1, column='o_project')
plt.title('初步轨道断面图')
plt.savefig(f'{imgfolder}plot1_track_sections.svg', format='svg')  # 修改保存路径和格式
plt.close(fig1)

# 图2：分割后的轨道线图
fig2 = plt.figure(figsize=(10, 8))
ax2 = fig2.add_subplot(111)
metro_line_splited.plot(ax=ax2, column='o_project')
plt.title('分割后的轨道线图')
plt.savefig(f'{imgfolder}plot2_splited_lines.svg', format='svg')  # 修改保存路径和格式
plt.close(fig2)

# 图3：四号线环线最后一段检查图
fig3 = plt.figure(figsize=(10, 8))
ax3 = fig3.add_subplot(111)
metro_line_splited[metro_line_splited['linename'] == '地铁4号线(内圈(宜山路-宜山路))'].iloc[-1:].plot(ax=ax3)
plt.title('四号线环线最后一段检查')
plt.savefig(f'{imgfolder}plot3_loop_check.svg', format='svg')  # 修改保存路径和格式
plt.close(fig3)

# 绘制最终客流蛛网图
fig4 = plt.figure(figsize=(10, 8), dpi=250)
ax4 = fig4.add_subplot(111)
plt.sca(ax4)

# 加载底图
bounds = [121.166, 30.966, 121.8, 31.483]
tbd.plot_map(plt, bounds, zoom=12, style=4)  # 使用 OpenStreetMap 风格

# 设置colormap
vmax = metro_line_parallel['count'].max()
cmapname = 'autumn_r'
cmap = matplotlib.colormaps.get_cmap(cmapname)

# 设置colorbar
cax = plt.axes([0.18, 0.4, 0.02, 0.3])
plt.title('人次')
plt.sca(ax4)

# 绘制轨道客流
metro_line_parallel.plot(
    ax=ax4, column='count',
    lw=metro_line_parallel['linewidth'] * 7,
    cmap=cmap, vmin=0, vmax=vmax,
    legend=True, cax=cax
)

plt.axis('off')
ax4.set_xlim(bounds[0], bounds[2] - 0.1)
ax4.set_ylim(bounds[1] + 0.05, bounds[3] - 0.1)
plt.title('早高峰8时客流量')

# 加比例尺和指北针
tbd.plotscale(ax4, bounds=bounds, textsize=10, compasssize=1, accuracy=1000, rect=[0.06, 0.13], zorder=10)

plt.savefig('final_passenger_flow.png')
plt.close(fig4)

