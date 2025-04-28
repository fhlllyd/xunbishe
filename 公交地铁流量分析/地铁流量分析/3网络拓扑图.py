import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt # 添加 matplotlib 导入

# --- 解决 Matplotlib 中文显示问题 ---
# 放在绘图相关操作之前
try:
    plt.rcParams['font.sans-serif'] = ['SimHei']  #尝试使用黑体
    plt.rcParams['axes.unicode_minus'] = False
except:
    print("警告：未能设置中文字体 'SimHei'。标题中的中文可能无法正确显示。")
    print("请确保你的系统安装了 'SimHei' 字体或尝试更换为其他可用中文字体，如 'Microsoft YaHei'。")
# --- 构建轨道网络 ---

# 读取轨道站点数据
try:
    stop = pd.read_csv(r'data/stop.csv')
except FileNotFoundError:
    print("错误：找不到文件 'data/stop.csv'。请确保文件路径正确。")
    exit() # 如果文件找不到，则退出脚本

# --- 第一部分：构建轨道边 (同一线路相邻站) ---

# 提取相邻站点信息用于构建边
stop['linename1'] = stop['linename'].shift(-1)
stop['stationnames1'] = stop['stationnames'].shift(-1)
# 保留同一线路的相邻站点对
stop = stop[stop['linename'] == stop['linename1']].copy() # 使用 .copy() 避免 SettingWithCopyWarning

# 提取线路名 (去除括号和"地铁"前缀)
stop['line'] = stop['linename'].apply(lambda r:r.split('(')[0].lstrip('地铁'))
# 特殊处理五号线支线，统一线路名为"5号线"
stop.loc[stop['line'] == '5号线支线', 'line'] = '5号线'

# 重命名列名以区分起点和终点
stop = stop.rename(columns = {'stationnames':'ostop','stationnames1':'dstop'})

# 构建唯一的站点名称 (线路名+站点名)，以区分不同线路的同名站
stop['ostation'] = stop['line'] + stop['ostop']
stop['dstation'] = stop['line'] + stop['dstop']

# 构建网络边的第一部分：轨道边
edge1 = stop[['ostation','dstation']].copy() # 使用 .copy() 避免 SettingWithCopyWarning
# 给轨道边添加权重，假定搭乘一个站点耗时3分钟
edge1['duration'] = 3

# --- 第二部分：构建换乘边 (不同线路同名站) ---

# (重新)计算唯一的站点名称 (基于 ostop，因为 stationnames 已被重命名)
# 注意：这里需要确保 stop DataFrame 包含 'line' 和 'ostop' 列
# 如果之前的 stop 被覆盖或修改，可能需要重新加载或调整逻辑
# 但基于原代码逻辑，我们继续使用当前的 stop DataFrame
stop['station'] = stop['line'] + stop['ostop'] # 使用 ostop

# 计算每个原始站点名 (ostop) 出现的次数，以识别换乘站
# 使用 ostop 进行分组，因为这是原始站点名
tmp_counts = stop.groupby(['ostop'])['linename'].count().rename('count').reset_index()

# 筛选出出现次数大于1的站点（理论上换乘站至少出现在2条线路，但代码用>2，沿用原逻辑）
# 注意：原代码是 > 2，这可能只选择3条或更多线路交汇的站，如果需要所有换乘站（2条及以上），应改为 > 1
transfer_stops_names = tmp_counts[tmp_counts['count'] > 1]['ostop'] # 沿用 > 1 或原 > 2 逻辑

# 筛选出原始 stop 数据中属于换乘站的行
tmp = pd.merge(stop, transfer_stops_names.to_frame(), on='ostop') # 合并以筛选

# 提取换乘站的 原始站点名(ostop), 线路(line), 唯一站点名(station)，并去重
tmp = tmp[['ostop', 'line', 'station']].drop_duplicates()

# 对换乘站信息进行自连接，以找出同一物理站点在不同线路上的表示
# 连接键是原始站点名 (ostop)
tmp = pd.merge(tmp, tmp, on='ostop')

# 提取换乘边：当两条记录属于同一个物理站点(ostop相同)但线路不同(line_x != line_y)时，
# 它们对应的唯一站点名(station_x, station_y)之间构成换乘边
edge2 = tmp[tmp['line_x'] != tmp['line_y']][['station_x', 'station_y']].copy() # 使用 .copy()
edge2.columns = ['ostation', 'dstation'] # 重命名列以匹配edge1
# 给换乘边添加权重，假定换乘耗时为5分钟
edge2['duration'] = 5

# --- 合并边并构建网络 ---

# 将轨道边和换乘边合并
# 使用 pd.concat 替代已弃用的 append
edge = pd.concat([edge1, edge2], ignore_index=True)

# 提取网络中的所有唯一节点 (从ostation和dstation两列提取更保险)
# node = list(edge['ostation'].drop_duplicates()) # 原方法只看 ostation
all_nodes = pd.concat([edge['ostation'], edge['dstation']]).unique()
node = list(all_nodes)


# 创建一个空图
G = nx.Graph()
# 添加节点
G.add_nodes_from(node)
# 添加带权重的无向边 (边列表需要是 (u, v, weight) 格式)
# edge.values 会产生 [ostation, dstation, duration] 的列表，符合要求
G.add_weighted_edges_from(edge[['ostation', 'dstation', 'duration']].values)

# --- 绘制网络图 ---
print("开始绘制网络图...")
plt.figure(figsize=(15, 15)) # 可以调整图形大小以便观察
nx.draw(G, node_size=10, width=0.5, with_labels=False) # 调小节点大小和边宽，不显示标签
plt.title("轨道交通网络图 (NetworkX)")
print("绘图完成，显示图形窗口...")
plt.show() # 在 .py 文件中必须调用 show() 来显示图形
#测试最短路径能否获取
print(nx.shortest_path(G, source='1号线黄陂南路', target='5号线东川路',weight='weight'))
print("脚本执行完毕。")