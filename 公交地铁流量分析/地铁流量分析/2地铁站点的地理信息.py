import pandas as pd
import geopandas
import matplotlib.pyplot as plt  # 导入绘图库

# 读取站点数据
stop = pd.read_csv(r'data/stop.csv')

# 去除重复站点名称（保留所有列）
stop = stop.drop_duplicates(subset=['stationnames'])

# 从站点经纬度信息生成地理信息列geometry，并将站点数据转换为GeoDataFrame
stop['geometry'] = geopandas.points_from_xy(stop['lon'], stop['lat'])
stop = geopandas.GeoDataFrame(stop)

# 绘制站点分布图
stop.plot()

# 保存为SVG格式到“图片”文件夹
plt.savefig('图片/站点分布图.svg', format='svg')

# 显示图像（可选）
plt.show()
