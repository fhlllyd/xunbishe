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

# 创建图片保存目录
if not os.path.exists('图片'):
    os.makedirs('图片')

# 读取公交线数据
shp = r'data/busline.json'
line = gpd.GeoDataFrame.from_file(shp, encoding='utf-8')

# 转换坐标系为投影坐标系，方便后面计算距离
line.crs = {'init': 'epsg:4326'}
line_2416 = line.to_crs(epsg=2416)
# 公交线路数据里面的 geometry
lineshp = line_2416['geometry'].iloc[0]
linename = line_2416['name'].iloc[0]

# 读取 GPS 数据
BUS_GPS_clean = gpd.read_file('BUS_GPS_clean.geojson')
BUS_GPS_clean_2416 = BUS_GPS_clean.to_crs(epsg=2416)
BUS_GPS = BUS_GPS_clean_2416.copy()
# 为 GPS 数据生成 project 列
BUS_GPS['project'] = BUS_GPS['geometry'].apply(lambda r: lineshp.project(r))

# 设定分析的时间范围
start_time = pd.to_datetime('2019-01-17 08:30:00')
end_time = pd.to_datetime('2019-01-17 10:30:00')
time_mask = (BUS_GPS['GPSDateTime'] >= start_time) & (BUS_GPS['GPSDateTime'] <= end_time)
BUS_GPS_time_filtered = BUS_GPS[time_mask]

# 计算每辆车在时间范围内的数据量
vehicle_counts = BUS_GPS_time_filtered.groupby('VehicleId').size().reset_index()
vehicle_counts.columns = ['VehicleId', 'count']
vehicle_counts = vehicle_counts.sort_values('count', ascending=False)

# 检查是否有足够的车辆数据
if len(vehicle_counts) == 0:
    print("警告: 在指定时间范围内没有任何车辆数据!")
    # 扩大时间范围重新尝试
    print("尝试扩大时间范围...")
    start_time = pd.to_datetime('2019-01-17 00:00:00')
    end_time = pd.to_datetime('2019-01-17 23:59:59')
    time_mask = (BUS_GPS['GPSDateTime'] >= start_time) & (BUS_GPS['GPSDateTime'] <= end_time)
    BUS_GPS_time_filtered = BUS_GPS[time_mask]
    
    # 重新计算车辆数据量
    vehicle_counts = BUS_GPS_time_filtered.groupby('VehicleId').size().reset_index()
    vehicle_counts.columns = ['VehicleId', 'count']
    vehicle_counts = vehicle_counts.sort_values('count', ascending=False)

# 选择数据量最多的车辆
if len(vehicle_counts) > 0:
    best_vehicle_id = vehicle_counts.iloc[0]['VehicleId']
    print(f"选择的车辆ID: {best_vehicle_id}, 数据条数: {vehicle_counts.iloc[0]['count']}")
    
    # 获取该车辆的所有数据（不限时间范围，方便后续分析）
    selected_vehicle_data = BUS_GPS[BUS_GPS['VehicleId'] == best_vehicle_id]
    # 获取该车辆在指定时间范围内的数据
    selected_vehicle_time_filtered = selected_vehicle_data[
        (selected_vehicle_data['GPSDateTime'] >= start_time) & 
        (selected_vehicle_data['GPSDateTime'] <= end_time)
    ]
    
    print(f"该车辆总数据条数: {len(selected_vehicle_data)}")
    print(f"在指定时间范围内的数据条数: {len(selected_vehicle_time_filtered)}")
    if len(selected_vehicle_data) > 0:
        print(f"时间范围: {selected_vehicle_data['GPSDateTime'].min()} 到 {selected_vehicle_data['GPSDateTime'].max()}")
    if len(selected_vehicle_time_filtered) > 0:
        print(f"指定时间范围内project值范围: {selected_vehicle_time_filtered['project'].min()} 到 {selected_vehicle_time_filtered['project'].max()}")
else:
    print("错误: 没有找到任何车辆数据!")
    selected_vehicle_data = pd.DataFrame()
    selected_vehicle_time_filtered = pd.DataFrame()
    best_vehicle_id = "未知"

# 读取站点位置数据
shp = r'data/busstop.json'
stop = gpd.GeoDataFrame.from_file(shp, encoding='utf-8')

# 转换坐标
stop.crs = {'init': 'epsg:4326'}
stop = stop.to_crs(epsg=2416)

# 地图匹配
stop['project'] = stop['geometry'].apply(lambda r: lineshp.project(r))
stop = stop[stop['linename'] == linename]

# 站点信息
print(f"站点数量: {len(stop)}")
if len(stop) > 0:
    print(f"站点project值范围: {stop['project'].min()} 到 {stop['project'].max()}")

# 只有当有足够数据时才绘图
if len(selected_vehicle_data) >= 2:  # 至少需要2个点才能画线
    # 绘制单车运行图 (不限时间)
    fig = plt.figure(1, (10, 6), dpi=250)
    ax1 = plt.subplot(111)
    plt.plot(selected_vehicle_data['GPSDateTime'], selected_vehicle_data['project'], 'b-', linewidth=1.5)
    plt.plot(selected_vehicle_data['GPSDateTime'], selected_vehicle_data['project'], 'ro', markersize=3)
    
    # 添加轴标签和标题
    plt.xlabel('时间', fontsize=12)
    plt.ylabel('位置 (投影坐标)', fontsize=12)
    plt.title(f'车辆 {best_vehicle_id} 全天运行轨迹', fontsize=14)
    
    # 格式化x轴日期显示
    plt.gcf().autofmt_xdate()
    
    plt.tight_layout()
    plt.savefig('图片/first_vehicle_run.svg', format='svg', bbox_inches='tight')
    plt.close()

    # 绘制单车运行图 (带站点标记，限定时间范围)
    if len(selected_vehicle_time_filtered) >= 2:
        fig = plt.figure(1, (10, 8), dpi=250)
        ax1 = plt.subplot(111)
        
        # 灰色线标注站点位置
        for i in range(len(stop)):
            project = stop['project'].iloc[i]
            stopname = stop['stopname'].iloc[i]
            plt.plot([start_time, end_time],
                    [project, project], 'k--', lw=0.2)
        
        # 绘制车辆运行轨迹
        plt.plot(selected_vehicle_time_filtered['GPSDateTime'], 
                selected_vehicle_time_filtered['project'], 
                'b-', linewidth=1.5, label=f'车辆 {best_vehicle_id}')
        plt.plot(selected_vehicle_time_filtered['GPSDateTime'], 
                selected_vehicle_time_filtered['project'], 
                'ro', markersize=3)
        
        # 标记站点名字
        plt.yticks(stop['project'], stop['stopname'])
        
        # 设定时间范围
        plt.xlim(start_time, end_time)
        
        # 添加轴标签和标题
        plt.xlabel('时间', fontsize=12)
        plt.ylabel('站点位置', fontsize=12)
        plt.title(f'车辆 {best_vehicle_id} 运行轨迹（含站点）', fontsize=14)
        
        # 格式化x轴日期显示
        plt.gcf().autofmt_xdate()
        
        # 添加图例
        plt.legend(loc='best')
        
        plt.tight_layout()
        plt.savefig('图片/first_vehicle_with_stops.svg', format='svg', bbox_inches='tight')
        plt.close()
    else:
        print(f"警告: 车辆 {best_vehicle_id} 在指定时间范围内数据点不足，无法绘制带站点的运行图")
else:
    print("错误: 没有足够的数据点绘制单车运行图")

# 绘制所有车的运行图 (限定时间范围)
fig = plt.figure(1, (10, 8), dpi=250)
ax1 = plt.subplot(111)

# 灰色线标注站点位置
for i in range(len(stop)):
    project = stop['project'].iloc[i]
    stopname = stop['stopname'].iloc[i]
    plt.plot([start_time, end_time],
             [project, project], 'k--', lw=0.2)

# 每辆车绘制一条运行图的曲线
vehicle_count = 0
for Vehicle in BUS_GPS_time_filtered['VehicleId'].drop_duplicates():
    vehicle_data = BUS_GPS_time_filtered[BUS_GPS_time_filtered['VehicleId'] == Vehicle]
    if len(vehicle_data) >= 2:  # 至少需要2个点才能画线
        plt.plot(vehicle_data['GPSDateTime'], vehicle_data['project'], linewidth=1, alpha=0.7)
        vehicle_count += 1

print(f"指定时间范围内有足够数据的车辆数: {vehicle_count}")

# 标记站点名字
plt.yticks(stop['project'], stop['stopname'])

# 设定时间范围
plt.xlim(start_time, end_time)

# 添加轴标签和标题
plt.xlabel('时间', fontsize=12)
plt.ylabel('站点位置', fontsize=12)
plt.title(f'所有车辆运行轨迹 ({start_time.strftime("%H:%M")} - {end_time.strftime("%H:%M")})', fontsize=14)

# 格式化x轴日期显示
plt.gcf().autofmt_xdate()

plt.tight_layout()
plt.savefig('图片/all_vehicles_run.svg', format='svg', bbox_inches='tight')
plt.close()

# 对车辆重新编号
BUS_GPS['GPSDateTime1'] = BUS_GPS['GPSDateTime'].shift()
BUS_GPS['VehicleId1'] = BUS_GPS['VehicleId'].shift()
# 如果时间间隔大于30分钟，则认为是新的车
duration = 30 * 60
BUS_GPS['flag'] = ((BUS_GPS['VehicleId1'] != BUS_GPS['VehicleId']) |
                   ((BUS_GPS['GPSDateTime'] - BUS_GPS['GPSDateTime1']).dt.total_seconds() > 
                   duration)).astype(int)
# 重新编号
BUS_GPS['VehicleId_new'] = BUS_GPS['flag'].cumsum()

# 使用 transbigdata 重新编号
BUS_GPS_reindex = tbd.id_reindex(BUS_GPS, 'VehicleId', timegap=1800, timecol='GPSDateTime')

# 筛选指定时间范围内的数据
BUS_GPS_reindex_time_filtered = BUS_GPS_reindex[
    (BUS_GPS_reindex['GPSDateTime'] >= start_time) & 
    (BUS_GPS_reindex['GPSDateTime'] <= end_time)
]

# 绘制重新编号后的所有车的运行图
fig = plt.figure(1, (10, 8), dpi=250)
ax1 = plt.subplot(111)

# 灰色线标注站点位置
for i in range(len(stop)):
    project = stop['project'].iloc[i]
    stopname = stop['stopname'].iloc[i]
    plt.plot([start_time, end_time],
             [project, project], 'k--', lw=0.2)

# 每辆车绘制一条运行图的曲线
vehicle_count = 0
for Vehicle in BUS_GPS_reindex_time_filtered['VehicleId_new'].drop_duplicates():
    vehicle_data = BUS_GPS_reindex_time_filtered[
        BUS_GPS_reindex_time_filtered['VehicleId_new'] == Vehicle
    ]
    if len(vehicle_data) >= 2:  # 至少需要2个点才能画线
        plt.plot(vehicle_data['GPSDateTime'], vehicle_data['project'], linewidth=1, alpha=0.7)
        vehicle_count += 1

print(f"重新编号后指定时间范围内有足够数据的车辆数: {vehicle_count}")

# 标记站点名字
plt.yticks(stop['project'], stop['stopname'])

# 设定时间范围
plt.xlim(start_time, end_time)

# 添加轴标签和标题
plt.xlabel('时间', fontsize=12)
plt.ylabel('站点位置', fontsize=12)
plt.title(f'重新编号后所有车辆运行轨迹 ({start_time.strftime("%H:%M")} - {end_time.strftime("%H:%M")})', 
          fontsize=14)

# 格式化x轴日期显示
plt.gcf().autofmt_xdate()

plt.tight_layout()
plt.savefig('图片/all_vehicles_reindexed_run.svg', format='svg', bbox_inches='tight')
plt.close()

print("图表绘制完成，请查看'图片'文件夹中的SVG文件。")


