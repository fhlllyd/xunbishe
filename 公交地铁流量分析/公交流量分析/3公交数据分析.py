import os
import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import transbigdata as tbd
import warnings
import matplotlib as mpl

# 设置 Matplotlib 显示中文和负号
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['font.serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 忽略SettingWithCopyWarning
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)
# 忽略FutureWarning
warnings.filterwarnings("ignore", category=FutureWarning)
# 忽略字体警告
warnings.filterwarnings("ignore", category=UserWarning, module='matplotlib')

# 设置中文字体
mpl.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun']
mpl.rcParams['font.serif'] = ['SimSun', 'SimHei']
mpl.rcParams['axes.unicode_minus'] = False
mpl.rcParams['font.family'] = 'sans-serif'

# 创建图片保存目录
os.makedirs("图片", exist_ok=True)

# 读取数据
BUS_GPS = pd.read_csv(r'data/busgps.csv', header=None)
BUS_GPS.columns = ['GPSDateTime', 'LineId', 'LineName', 'NextLevel', 'PrevLevel',
                   'Strlatlon', 'ToDir', 'VehicleId', 'VehicleNo', 'unknow']
# 时间转换为datetime格式
BUS_GPS['GPSDateTime'] = pd.to_datetime(BUS_GPS['GPSDateTime'])

# 切分经纬度的字符串
BUS_GPS['lon'] = BUS_GPS['Strlatlon'].apply(lambda r: r.split(',')[0])
BUS_GPS['lat'] = BUS_GPS['Strlatlon'].apply(lambda r: r.split(',')[1])
# 坐标系转换
BUS_GPS['lon'], BUS_GPS['lat'] = tbd.gcj02towgs84(BUS_GPS['lon'].astype(float), BUS_GPS['lat'].astype(float))

# 读取公交线路数据
shp = r'data/busline.json'
linegdf = gpd.GeoDataFrame.from_file(shp, encoding='utf-8')
line = linegdf.iloc[:1].copy()
# 第一张图: 线路图
fig1, ax1 = plt.subplots(figsize=(8, 4), dpi=250)
line.plot(ax=ax1)
plt.title('公交线路图')
plt.savefig("图片/公交线路图.svg", format="svg")
plt.close(fig1)

# 读取公交站点数据
shp = r'data/busstop.json'
stop = gpd.GeoDataFrame.from_file(shp, encoding='utf-8')
stop = stop[stop['linename'] == '71路(延安东路外滩-申昆路枢纽站)']
# 第二张图: 站点图
fig2, ax2 = plt.subplots(figsize=(8, 4), dpi=250)
stop.plot(ax=ax2)
plt.title('公交站点图')
plt.savefig("图片/公交站点图.svg", format="svg")
plt.close(fig2)

# 计算到站信息
arriveinfo = tbd.busgps_arriveinfo(BUS_GPS, line, stop)

# 根据函数签名正确调用，只传递前三个必要参数，让col使用默认值
onewaytime = tbd.busgps_onewaytime(
    arriveinfo,          # 第一个参数是arrive_info
    '延安东路外滩',      # 第二个参数是start
    '申昆路枢纽站'       # 第三个参数是end
)

# 打印列名和前几行数据，以便了解数据结构
print("onewaytime列名:", onewaytime.columns.tolist())
print("onewaytime前5行:", onewaytime.head())

# 检查是否有方向相关的列
direction_column = 'direction'  # 默认方向列名，可能需要修改
if 'direction' in onewaytime.columns:
    direction_column = 'direction'
elif 'dir' in onewaytime.columns:
    direction_column = 'dir'
elif 'Direction' in onewaytime.columns:
    direction_column = 'Direction'
elif '方向' in onewaytime.columns:
    direction_column = '方向'
else:
    # 如果没有找到方向列，创建一个默认方向列
    print("未找到方向列，创建默认方向")
    onewaytime['direction'] = '前往' + onewaytime['endstop']
    direction_column = 'direction'

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['font.serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 第三张图: 耗时分布箱型图
fig3 = plt.figure(figsize=(8, 4), dpi=250)
ax3 = plt.subplot(111)
sns.boxplot(x='shour', y=onewaytime['duration'] / 60, hue=direction_column, data=onewaytime, ax=ax3)
plt.ylabel('始发站至终点站耗时（分钟）')
plt.xlabel('小时')
plt.ylim(0)
plt.title('公交耗时分布')
plt.savefig("图片/公交耗时分布.svg", format="svg")
plt.close(fig3)

# 转换坐标系为投影坐标系，方便后面计算距离
line.crs = {'init': 'epsg:4326'}
line_2416 = line.to_crs(epsg=2416)
# 公交线路数据里面的geometry
lineshp = line_2416['geometry'].iloc[0]
linename = line_2416['name'].iloc[0]

# 筛选去掉车速过快的
# 车速单位转换为km/h
onewaytime['speed'] = (lineshp.length/onewaytime['duration'])*3.6
onewaytime = onewaytime[onewaytime['speed'] <= 60]

# 第四张图: 车速分布
fig4 = plt.figure(figsize=(8, 4), dpi=250)
ax4 = plt.subplot(111)
sns.boxplot(x='shour', y='speed', hue=direction_column, data=onewaytime, ax=ax4)
plt.ylabel('运营速度（km/h）')
plt.xlabel('小时')
plt.ylim(0)
plt.title('公交车速分布')
plt.savefig("图片/公交车速分布.svg", format="svg")
plt.close(fig4)

print("所有图片已保存到'图片'文件夹中")