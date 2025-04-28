import json

import geopandas as gpd
import pandas as pd
import requests
from shapely import LineString

# 通过高德地图爬取数据
url = 'https://map.amap.com/service/subway?_1707368894338&srhdata=3100_drw_shanghai.json'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 '
                  'Safari/537.36 Edg/121.0.0.0'
}
response = requests.get(url=url, headers=headers)

# 将返回结果转为json格式
result = json.loads(response.text)

# 创建空列表存储站点和线路的数据
stop_data = []
line_data = gpd.GeoDataFrame()

# 存储线路的名字和经纬度数据
names = []
lon_lat_s = []

# 遍历数据
for item in result['l']:
    # 提取线路名字，线路起点和终点
    line_name = item['kn']
    line_direction = '({start}-{end})'
    start = item['st'][0]['n']
    end = item['st'][-1]['n']

    lon_lat = []
    names.append(line_name)

    x = item['x']

    total = len(item['st'])
    num = 1
    for sub_item in item['st']:
        # 提取站点名字和站点经纬度
        n_data = sub_item['n']
        sl_data = sub_item['sl']
        sl_data_parts = sl_data.split(',')
        sl_data_A = sl_data_parts[0]
        sl_data_B = sl_data_parts[1]

        lon_lat.append(sl_data_parts)

        # 创建包含站点数据的字典（正方向）
        extracted_item_0 = {
            'name': n_data,
            'linename': line_name + line_direction.format(start=start, end=end),
            'lon': sl_data_A,
            'lat': sl_data_B,
            'x': x,
            'num': num,
            'direction': 1
        }
        # 创建包含站点数据的字典（反方向）
        extracted_item_1 = {
            'name': n_data,
            'linename': line_name + line_direction.format(start=end, end=start),
            'lon': sl_data_A,
            'lat': sl_data_B,
            'x': x,
            'num': total - num + 1,
            'direction': 2
        }
        stop_data.append(extracted_item_0)
        stop_data.append(extracted_item_1)
        num += 1

    lon_lat_s.append(LineString(lon_lat))

# 将站点数据保存为JSON格式并保存
json_output = json.dumps(stop_data, indent=4, ensure_ascii=False)
with open('地铁数据/stop.json', 'w', encoding='utf-8') as f:
    f.write(json_output)


# 若修改了保存路径，则此处需要修改成自己保存文件的路径
stop = pd.read_json(r'地铁数据/stop.json', encoding='utf-8')
stop = stop.sort_values(by=['direction', 'x', 'num'])
# 若修改了保存路径，则此处需要修改为保存的路径
stop.to_json(r'地铁数据/stop.json', force_ascii=False)


# 保存线路数据
line_data['name'] = names
line_data.set_geometry(lon_lat_s, inplace=True)

# 此处可以将line.shp修改成自己的保存路径
line_data.to_file("地铁数据/line.shp", encoding='utf-8')
