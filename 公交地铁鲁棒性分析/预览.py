import geopandas as gpd
import matplotlib.pyplot as plt

# 加载保存的SHP文件
line_data = gpd.read_file("地铁数据/line.shp")

# 使用plot方法预览
line_data.plot()

# 显示图形
plt.show()
