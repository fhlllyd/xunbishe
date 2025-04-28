import geopandas as gpd
import matplotlib.pyplot as plt

# 读取地铁线路GIS文件
line = gpd.read_file('data/line.json', encoding='utf-8')
# 绘制地铁线路图
line.plot()
# 保存图片为SVG格式
plt.savefig('图片/地铁线路图.svg', format='svg')
# 显示图片（可选）
plt.show()
