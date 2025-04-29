
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import geopandas as gpd
import transbigdata as tbd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# 设置 Matplotlib 显示中文和负号
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['font.serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 创建“图片”文件夹
if not os.path.exists("图片"):
    os.makedirs("图片")
def clean_same(df, col):
    df = df.sort_values(by=['VehicleId', 'GPSDateTime']).reset_index(drop=True)
    check_cols = [c for c in col if c != 'GPSDateTime']
    keep_indices = []
    for _, group in df.groupby('VehicleId'):
        group['diff'] = group[check_cols].ne(group[check_cols].shift()).any(axis=1)
        group['block'] = (group['diff'] | group['diff'].shift(fill_value=True)).cumsum()
        for _, block in group.groupby('block'):
            if len(block) > 1:
                keep_indices.extend([block.index[0], block.index[-1]])
            else:
                keep_indices.append(block.index[0])
    return df.loc[sorted(set(keep_indices))].drop(columns=['diff', 'block'], errors='ignore')
# 设置 matplotlib 的中文显示
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['font.serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 读取 GPS 数据
BUS_GPS = pd.read_csv(r'data/busgps.csv', header=None)
BUS_GPS.columns = ['GPSDateTime', 'LineId', 'LineName', 'NextLevel', 'PrevLevel',
                   'Strlatlon', 'ToDir', 'VehicleId', 'VehicleNo', 'unknow']

# 时间转换为 datetime 格式
BUS_GPS['GPSDateTime'] = pd.to_datetime(BUS_GPS['GPSDateTime'])

# 读取公交线数据
shp = r'data/busline.json'
line = gpd.GeoDataFrame.from_file(shp, encoding='utf-8')

# 读取公交站点数据
shp = r'data/busstop.json'
stop = gpd.GeoDataFrame.from_file(shp, encoding='utf-8')

# 切分经纬度的字符串
BUS_GPS['lon'] = BUS_GPS['Strlatlon'].apply(lambda r: r.split(',')[0])
BUS_GPS['lat'] = BUS_GPS['Strlatlon'].apply(lambda r: r.split(',')[1])
# 坐标系转换
BUS_GPS['lon'], BUS_GPS['lat'] = tbd.gcj02towgs84(BUS_GPS['lon'].astype(float), BUS_GPS['lat'].astype(float))

# 一辆车在一个时刻只保留一条记录
BUS_GPS_clean = BUS_GPS.drop_duplicates(subset=['VehicleId', 'GPSDateTime'])

# 采样间隔的统计
BUS_GPS_clean = BUS_GPS_clean.sort_values(by=['VehicleId', 'GPSDateTime'])
# 将数据复制一份，避免计算采样间隔时影响到数据
BUS_GPS_tmp = BUS_GPS_clean.copy()
# 将下一条数据上移一行
BUS_GPS_tmp['VehicleId1'] = BUS_GPS_tmp['VehicleId'].shift(-1)
BUS_GPS_tmp['GPSDateTime1'] = BUS_GPS_tmp['GPSDateTime'].shift(-1)
# 计算时间差，即采样间隔
BUS_GPS_tmp['duration'] = (BUS_GPS_tmp['GPSDateTime1'] - BUS_GPS_tmp['GPSDateTime']).dt.total_seconds()
# 仅保留同一辆车的记录
BUS_GPS_tmp = BUS_GPS_tmp[BUS_GPS_tmp['VehicleId1'] == BUS_GPS_tmp['VehicleId']]

# 使用 tbd.sample_duration 方法，输入车辆 ID 与时间所在列，同样可计算数据采样间隔
sample_duration = tbd.sample_duration(BUS_GPS_clean, col=['VehicleId', 'GPSDateTime'])

# 绘制采样间隔的核密度分布
fig = plt.figure(figsize=(7, 4), dpi=250)
ax1 = plt.subplot(111)
sns.kdeplot(sample_duration[sample_duration['duration'] < 60]['duration'])
plt.xlim(0, 60)
plt.xticks(range(0, 60, 5), range(0, 60, 5))
plt.xlabel('采样间隔（秒）')
plt.ylabel('概率密度分布')
plt.savefig('图片/sample_duration_kde.svg', format='svg', bbox_inches='tight')
plt.close()

# 使用自定义函数清理数据
BUS_GPS_clean = clean_same(BUS_GPS_clean, col=['VehicleId', 'GPSDateTime', 'lon', 'lat'])

# 将数据转换为 GeoDataFrame，以便进行地图匹配
BUS_GPS_clean['geometry'] = gpd.points_from_xy(BUS_GPS_clean['lon'], BUS_GPS_clean['lat'])
BUS_GPS_clean = gpd.GeoDataFrame(BUS_GPS_clean)

# 转换坐标系为投影坐标系，方便后面计算距离
BUS_GPS_clean.crs = {'init': 'epsg:4326'}

BUS_GPS_clean.to_file('BUS_GPS_clean.geojson', driver='GeoJSON', encoding='utf-8')
BUS_GPS_clean_2416 = BUS_GPS_clean.to_crs(epsg=2416)

# 转换坐标系为投影坐标系，方便后面计算距离
line.crs = {'init': 'epsg:4326'}
line_2416 = line.to_crs(epsg=2416)
# 公交线路数据里面的 geometry
lineshp = line_2416['geometry'].iloc[0]
linename = line_2416['name'].iloc[0]

# 利用 project 方法，将数据点投影至公交线路上
BUS_GPS_clean_2416['project'] = BUS_GPS_clean_2416['geometry'].apply(lambda r: lineshp.project(r))
# 原始的坐标点存储在一个字段中
BUS_GPS_clean_2416['geometry_orgin'] = BUS_GPS_clean_2416['geometry']
# 利用 interpolate 方法，生成匹配的坐标点
BUS_GPS_clean_2416['geometry'] = BUS_GPS_clean_2416['project'].apply(lambda r: lineshp.interpolate(r))
# 计算原始点和匹配点之间的距离
BUS_GPS_clean_2416['diff'] = BUS_GPS_clean_2416.apply(lambda r: r['geometry_orgin'].distance(r['geometry']), axis=1)

# 绘制距离分布的核密度分布
fig = plt.figure(figsize=(7, 4), dpi=250)
ax1 = plt.subplot(111)
sns.kdeplot(BUS_GPS_clean_2416[BUS_GPS_clean_2416['diff'] < 1000]['diff'])
plt.xticks(range(0, 1000, 100), range(0, 1000, 100))
plt.ylabel('概率密度分布')
plt.xlabel('距离(米)')
plt.savefig('图片/distance_kde.svg', format='svg', bbox_inches='tight')
plt.close()

# 只筛选保留距离公交线路 200 米内的坐标点
BUS_GPS_clean_2416 = BUS_GPS_clean_2416[BUS_GPS_clean_2416['diff'] < 200]

# 地图匹配后的匹配点
fig = plt.figure(figsize=(7, 4), dpi=250)
ax = plt.subplot(111)
BUS_GPS_clean_2416.plot(ax=ax)
plt.savefig('图片/matched_points.svg', format='svg', bbox_inches='tight')
plt.close()

# 地图匹配后的原始点
tmp = BUS_GPS_clean_2416[['geometry_orgin']]
tmp.columns = ['geometry']
fig = plt.figure(figsize=(7, 4), dpi=250)
ax = plt.subplot(111)
gpd.GeoDataFrame(tmp).plot(ax=ax)
plt.savefig('图片/original_points.svg', format='svg', bbox_inches='tight')
plt.close()

# 对公交线做缓冲区
line.crs = {'init': 'epsg:4326'}
line_buffer = line.to_crs(epsg=2416)
line_buffer['geometry'] = line_buffer.buffer(200)
line_buffer = line_buffer.to_crs(epsg=4326)

# 绘制缓冲区
fig = plt.figure(figsize=(7, 4), dpi=250)
ax = plt.subplot(111)
line_buffer.plot(ax=ax)
plt.savefig('图片/line_buffer.svg', format='svg', bbox_inches='tight')
plt.close()

# tbd.clean_outofshape 方法剔除公交线路缓冲区范围外的数据
BUS_GPS_clean_2 = tbd.clean_outofshape(BUS_GPS_clean, line_buffer, col=['lon', 'lat'], accuracy=100)

# 绘制清理后的数据
fig = plt.figure(figsize=(7, 4), dpi=250)
ax = plt.subplot(111)
BUS_GPS_clean_2.plot(ax=ax)
plt.savefig('图片/cleaned_data.svg', format='svg', bbox_inches='tight')
plt.close()

