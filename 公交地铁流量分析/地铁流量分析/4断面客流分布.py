# 导入所需库
import os

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

# 设置 Matplotlib 显示中文和负号
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['font.serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# --- 读取轨道站点数据 ---
try:
    stop = pd.read_csv(r'data/stop.csv')
    print("成功读取 'data/stop.csv'")
except FileNotFoundError:
    print("错误：找不到文件 'data/stop.csv'。请确保文件存在于 'data' 子目录中，且脚本从正确的父目录运行。")
    exit()  # 如果文件找不到，则退出脚本

# --- 第一部分：构建轨道边 (同一线路相邻站) ---
print("第一部分：构建轨道边...")
# 提取相邻站点信息用于构建边
stop['linename1'] = stop['linename'].shift(-1)
stop['stationnames1'] = stop['stationnames'].shift(-1)
# 保留同一线路的相邻站点对
stop = stop[stop['linename'] == stop['linename1']].copy() # 使用 .copy() 避免 SettingWithCopyWarning

# 提取线路名 (去除括号和"地铁"前缀)
stop['line'] = stop['linename'].apply(lambda r: r.split('(')[0].lstrip('地铁'))
# 特殊处理五号线支线，统一线路名为"5号线"
stop.loc[stop['line'] == '5号线支线', 'line'] = '5号线'

# 重命名列名以区分起点和终点
stop = stop.rename(columns={'stationnames': 'ostop', 'stationnames1': 'dstop'})

# 构建唯一的站点名称 (线路名+站点名)，以区分不同线路的同名站
stop['ostation'] = stop['line'] + stop['ostop']
stop['dstation'] = stop['line'] + stop['dstop']

# 构建网络边的第一部分：轨道边
edge1 = stop[['ostation', 'dstation']].copy() # 使用 .copy() 避免 SettingWithCopyWarning
# 给轨道边添加权重，假定搭乘一个站点耗时3分钟
edge1['duration'] = 3
print(f"轨道边构建完成，共 {len(edge1)} 条。")

# --- 第二部分：构建换乘边 (不同线路同名站) ---
print("第二部分：构建换乘边...")
# (重新)计算唯一的站点名称 (基于 ostop)
# 注意：确保 stop DataFrame 包含 'line' 和 'ostop' 列
stop['station'] = stop['line'] + stop['ostop'] # 使用 ostop

# 计算每个原始站点名 (ostop) 出现的次数，以识别换乘站
tmp_counts = stop.groupby(['ostop'])['linename'].count().rename('count').reset_index()

# 筛选出出现次数大于1的站点（即换乘站）
transfer_stops_names = tmp_counts[tmp_counts['count'] > 1]['ostop']

# 筛选出原始 stop 数据中属于换乘站的行
tmp = pd.merge(stop, transfer_stops_names.to_frame(), on='ostop') # 合并以筛选

# 提取换乘站的 原始站点名(ostop), 线路(line), 唯一站点名(station)，并去重
tmp = tmp[['ostop', 'line', 'station']].drop_duplicates()

# 对换乘站信息进行自连接，以找出同一物理站点在不同线路上的表示
tmp = pd.merge(tmp, tmp, on='ostop')

# 提取换乘边：当两条记录属于同一个物理站点但线路不同时
edge2 = tmp[tmp['line_x'] != tmp['line_y']][['station_x', 'station_y']].copy() # 使用 .copy()
edge2.columns = ['ostation', 'dstation'] # 重命名列以匹配edge1
# 给换乘边添加权重，假定换乘耗时为5分钟
edge2['duration'] = 5
print(f"换乘边构建完成，共 {len(edge2)} 条。")

# --- 合并边并构建网络 ---
print("合并边并构建网络...")
# 将轨道边和换乘边合并
edge = pd.concat([edge1, edge2], ignore_index=True)
print(f"总边数：{len(edge)}")

# 提取网络中的所有唯一节点
all_nodes = pd.concat([edge['ostation'], edge['dstation']]).unique()
node = list(all_nodes)
print(f"总节点数：{len(node)}")

# 创建一个空图
G = nx.Graph()
# 添加节点
G.add_nodes_from(node)
# 添加带权重的无向边
G.add_weighted_edges_from(edge[['ostation', 'dstation', 'duration']].values)
print("NetworkX 图构建完成。")

# --- 读取和处理IC卡刷卡数据 ---
print("读取和处理IC卡数据...")
try:
    icdata = pd.read_csv(r'data/icdata-sample.csv', header=None)
    print("成功读取 'data/icdata-sample.csv'")
except FileNotFoundError:
    print("错误：找不到文件 'data/icdata-sample.csv'。请确保文件存在于 'data' 子目录中。")
    exit()

icdata.columns = ['cardid', 'date', 'time', 'station', 'mode', 'price', 'type']

# 提取其中地铁刷卡部分
metrodata = icdata[icdata['mode'] == '地铁'].copy() # 使用 .copy()
# 按卡号时间排序
metrodata = metrodata.sort_values(by=['cardid', 'date', 'time'])
# 将数据整体往上移一行赋值给新的列
for i in metrodata.columns:
    metrodata[i + '1'] = metrodata[i].shift(-1)
# 每条出行只保留一条记录 (进站价格为0，出站价格大于0)
metrood = metrodata[(metrodata['cardid'] == metrodata['cardid1']) &
                    (metrodata['price'] == 0) &
                    (metrodata['price1'] > 0)].copy() # 使用 .copy()

# 提取起终点的线路和站点
metrood['oline'] = metrood['station'].apply(lambda r: r[:(r.find('线') + 1)])
metrood['ostation_name'] = metrood['station'].apply(lambda r: r[(r.find('线') + 1):]) # 临时存储原始站名
metrood['dline'] = metrood['station1'].apply(lambda r: r[:(r.find('线') + 1)])
metrood['dstation_name'] = metrood['station1'].apply(lambda r: r[(r.find('线') + 1):]) # 临时存储原始站名

# 保留有用的列，并重命名列
metrood = metrood[['cardid', 'date', 'time', 'station', 'oline', 'ostation_name', 'time1', 'station1', 'dline', 'dstation_name']]
metrood.columns = ['cardid', 'date', 'otime', 'ostation_raw', 'oline', 'ostop', 'dtime', 'dstation_raw', 'dline', 'dstop']

# --- 修正IC卡数据中的站点名称 ---
print("修正IC卡数据中的站点名称...")
corrections = {
    '淞浜路': '淞滨路',
    '上海大学站': '上海大学',
    '上海野生动物园': '野生动物园',
    '外高桥保税区北': '外高桥保税区北站',
    '外高桥保税区南': '外高桥保税区南站',
    '李子园路': '李子园'
}
metrood['ostop'] = metrood['ostop'].replace(corrections)
metrood['dstop'] = metrood['dstop'].replace(corrections)

# 字符串左右去除空格
metrood['ostop'] = metrood['ostop'].str.strip()
metrood['dstop'] = metrood['dstop'].str.strip()

# 构建修正后的站点名称（带线路名称），用于匹配网络节点
metrood['ostation'] = metrood['oline'] + metrood['ostop']
metrood['dstation'] = metrood['dline'] + metrood['dstop']

# 保存处理后的OD数据
try:
    metrood.to_csv(r'data/metrood.csv', index=None, encoding='utf-8-sig')
    print("处理后的OD数据已保存到 'data/metrood.csv'")
except Exception as e:
    print(f"保存 'data/metrood.csv' 时出错: {e}")


# --- 计算最短路径 ---
print("计算OD对的最短路径...")
# 获取去重后的OD对
od_distinct = metrood[['ostation', 'dstation']].drop_duplicates().copy() # 使用 .copy()

# 定义一个函数来安全地计算路径，处理可能找不到节点的情况
def get_shortest_path(graph, source, target, weight):
    try:
        # 检查节点是否存在于图中
        if source not in graph:
            # print(f"警告: 起点 '{source}' 不在图中。")
            return None
        if target not in graph:
            # print(f"警告: 终点 '{target}' 不在图中。")
            return None
        # 计算最短路径
        return nx.shortest_path(graph, source=source, target=target, weight=weight)
    except nx.NetworkXNoPath:
        # print(f"警告: 无法找到从 '{source}' 到 '{target}' 的路径。")
        return None
    except Exception as e:
        print(f"计算路径时发生错误 ({source} -> {target}): {e}")
        return None

# 对去重后的OD遍历，得到每条OD的出行路径
# **重要修正**: weight参数应为 'duration'
od_distinct['path'] = od_distinct.apply(
    lambda r: get_shortest_path(G, source=r['ostation'], target=r['dstation'], weight='duration'),
    axis=1
)

# 过滤掉没有找到路径的OD对
od_distinct = od_distinct.dropna(subset=['path'])
print(f"为 {len(od_distinct)} 条有效OD对计算了最短路径。")

# --- 构建OD路径分段表 ---
print("构建OD路径分段表...")
# 先创建空的list
ls = []
# 遍历有路径的OD对
for i in range(len(od_distinct)):
    # 获取其中的一行
    r = od_distinct.iloc[i]
    # 对这一行的路径构建轨道段的表
    path_nodes = r['path']
    if len(path_nodes) > 1: # 路径至少需要2个节点才能构成段
        tmp = pd.DataFrame({'o': path_nodes[:-1], 'd': path_nodes[1:]})
        # 对这个表添加O和D列
        tmp['ostation'] = r['ostation']
        tmp['dstation'] = r['dstation']
        # 将这个表添加到空list里
        ls.append(tmp)

# 合并list里面的表，变成一个大的出行路径表
if ls: # 检查列表是否为空
    od_path = pd.concat(ls)
    print(f"OD路径分段表构建完成，共 {len(od_path)} 个路段。")
    # 保存
    try:
        od_path.to_csv(r'data/od_path.csv', index=None, encoding='utf-8-sig')
        print("路径分段数据已保存到 'data/od_path.csv'")
    except Exception as e:
        print(f"保存 'data/od_path.csv' 时出错: {e}")
else:
    print("警告：未能生成任何有效的OD路径分段。后续分析可能无法进行。")
    od_path = pd.DataFrame(columns=['o', 'd', 'ostation', 'dstation']) # 创建空DataFrame以避免后续错误


# --- 分析8点断面客流 ---
print("开始分析8点断面客流...")
# 确保 od_path 存在且不为空
if not od_path.empty:
    # 为OD添加小时的列
    metrood['Hour'] = metrood['otime'].apply(lambda r: r.split(':')[0])

    # 提取8点的OD，并将OD与出行路径表连接
    trips_08 = metrood[metrood['Hour'] == '08'].copy() # 使用 .copy()
    print(f"提取到 {len(trips_08)} 条8点出发的行程。")

    # 使用 inner merge，只保留那些成功计算了路径的行程
    tmp = pd.merge(trips_08, od_path, on=['ostation', 'dstation'])
    print(f"合并行程与路径后，得到 {len(tmp)} 条有效路径段记录。")


    # 集计得到每个轨道段的客流量
    if not tmp.empty:
        metro_passenger = tmp.groupby(['o', 'd'])['cardid'].count().rename('count').reset_index()

        print(f"计算得到 {len(metro_passenger)} 个轨道段的8点客流量。")

        # 保存 metro_passenger 数据到 CSV 文件
        try:
            metro_passenger.to_csv(r'data/metro_passenger.csv', index=None, encoding='utf-8-sig')
            print("轨道段客流量数据已保存到 'data/metro_passenger.csv'")
        except Exception as e:
            print(f"保存 'data/metro_passenger.csv' 时出错: {e}")

        # --- 绘制指定线路断面客流图 ---
        print("绘制断面客流图...")
        # 指定线路
        linename = '2号线'
        # 筛选出指定线路的站点信息 (从原始 stop 数据重新筛选，确保数据干净)
        # 需要重新加载或使用原始 stop 副本，因为之前的 stop 被修改过
        # 为了简单起见，我们假设之前的 stop 变量仍然包含需要的信息
        # 但最佳实践是重新过滤原始数据
        try:
            stop_orig = pd.read_csv(r'data/stop.csv') # 重新加载以获取干净数据
            stop_orig['line'] = stop_orig['linename'].apply(lambda r: r.split('(')[0].lstrip('地铁'))
            stop_orig.loc[stop_orig['line'] == '5号线支线', 'line'] = '5号线'
            linestop_base = stop_orig[stop_orig['line'] == linename].copy()
        except FileNotFoundError:
            print("错误：无法重新读取 'data/stop.csv' 以获取线路信息。")
            exit()
        except KeyError as e:
             print(f"错误: 处理 stop_orig 时列名 '{e}' 不存在。检查 'data/stop.csv' 文件格式。")
             exit()


        # 构建轨道断面 (同一线路相邻站)
        linestop = linestop_base.copy() # 操作副本
        linestop['linename1'] = linestop['linename'].shift(-1)
        linestop['stationnames1'] = linestop['stationnames'].shift(-1)
        linestop = linestop[linestop['linename'] == linestop['linename1']].copy() # 再次使用 .copy()

        # 构建断面名称，使其与集计数据能够对应
        linestop['o'] = linestop['line'] + linestop['stationnames']
        linestop['d'] = linestop['line'] + linestop['stationnames1'] # 使用修改后的 stationnames1
        # 选择需要的列
        linestop = linestop[['o', 'd', 'stationnames', 'stationnames1', 'linename', 'linename1']].copy()

        # 匹配断面客流 (使用 left merge 保留所有线路分段，即使客流为0)
        linestop = pd.merge(linestop, metro_passenger, on=['o', 'd'], how='left')
        # 将 NaN (无客流) 替换为 0
        linestop['count'] = linestop['count'].fillna(0)

        # 检查是否有数据用于绘图
        if linestop.empty:
            print(f"警告：未能匹配到线路 '{linename}' 的客流数据。无法绘制图形。")
        else:
            # 分离上下行数据
            unique_linenames = linestop['linename'].drop_duplicates()
            if len(unique_linenames) < 2:
                print(f"警告：线路 '{linename}' 数据不包含明确的上下行信息（需要至少两个不同的linename）。")
                # 尝试基于第一个 linename 绘制单向
                shangxing_data = linestop.copy()
                shangxing_data['x'] = range(len(shangxing_data))
                xiaxing_data = pd.DataFrame(columns=shangxing_data.columns) # 创建空的，避免绘图错误
                shangxing_label = unique_linenames.iloc[0] if not unique_linenames.empty else linename
                xiaxing_label = ""

            else:
                 # 提取上行客流
                shangxing_label = unique_linenames.iloc[0]
                shangxing_data = linestop[linestop['linename'] == shangxing_label].copy()
                shangxing_data['x'] = range(len(shangxing_data))

                # 提取下行客流
                xiaxing_label = unique_linenames.iloc[1]
                xiaxing_data = linestop[linestop['linename'] == xiaxing_label].copy()
                 # 确保下行数据按相反顺序排列 x 轴
                xiaxing_data = xiaxing_data.sort_index(ascending=False).reset_index(drop=True) # 按地理反向排序
                xiaxing_data['x'] = range(len(xiaxing_data)) # 重新编号 x


            # 提取站点名称 (基于上行数据，假设上下行站点顺序对应)
            if not shangxing_data.empty:
                stationnames = list(shangxing_data['stationnames'])
                stationnames.append(shangxing_data['stationnames1'].iloc[-1])
                x_ticks_positions = np.arange(len(stationnames)) - 0.5
            else: # 如果没有上行数据，尝试用下行数据（反向）
                 if not xiaxing_data.empty:
                     stationnames = list(xiaxing_data['stationnames1']) # 下行的终点是上行的起点
                     stationnames.append(xiaxing_data['stationnames'].iloc[-1])
                     stationnames.reverse() # 反转顺序以匹配地理
                     x_ticks_positions = np.arange(len(stationnames)) - 0.5
                 else:
                     stationnames = []
                     x_ticks_positions = []
                     print("警告：无法提取站点名称用于绘图。")


            # 上下行数据扩样25倍
            scaling_factor = 25
            shangxing_data['count'] *= scaling_factor
            xiaxing_data['count'] *= scaling_factor

            # 绘制
            fig = plt.figure(1, (10, 6), dpi=300) # 调整图形大小和分辨率
            ax1 = plt.subplot(111)

            # 绘制上下行断面客流
            if not shangxing_data.empty:
                plt.bar(shangxing_data['x'], shangxing_data['count'], width=0.4, label=shangxing_label)
            if not xiaxing_data.empty:
                # 绘制下行客流为负值
                plt.bar(xiaxing_data['x'], -xiaxing_data['count'], width=0.4, label=xiaxing_label)

            # 图框上轴、右轴不显示，图框的下轴放在y轴为0的地方
            ax1.spines['bottom'].set_position(('data', 0))
            ax1.spines['top'].set_color('none')
            ax1.spines['right'].set_color('none')

            # 标注站点名称
            if stationnames:
                 plt.xticks(x_ticks_positions, stationnames, rotation=90, size=8)
            else:
                 plt.xticks([]) # 不显示刻度

            # 图例显示与xy轴标题
            plt.legend()
            plt.ylabel(f'断面客流 (原始值 x {scaling_factor})') # 标注扩样因子
            plt.xlabel('站点')

            # 调整y轴显示刻度，不显示负号
            locs, labels = plt.yticks()
            plt.yticks(locs, abs(locs.astype(int)))

            # 定义图名
            plt.title(f'{linename} 8时断面客流')
            plt.tight_layout() # 调整布局防止标签重叠

            # 确保“图片”文件夹存在
            output_folder = '图片'
            os.makedirs(output_folder, exist_ok=True)  # 如果文件夹不存在则创建

            # 保存为 SVG 格式
            svg_filename = os.path.join(output_folder, f'{linename}_8时断面客流.svg')
            plt.savefig(svg_filename, format='svg')  # 保存为 SVG 文件
            print(f"断面客流图已保存为 SVG 文件：{svg_filename}")

            # 显示图形（可选）
            plt.show()
            print("断面客流图绘制完成并显示。")

    else:
        print("警告：没有计算出有效的轨道段客流量，无法绘制断面图。")

else:
    print("警告：OD路径分段表为空，无法进行客流分析和绘图。")

print("脚本执行完毕。")