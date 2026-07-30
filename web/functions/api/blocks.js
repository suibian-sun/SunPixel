// Cloudflare Pages Function - 获取可用方块类型列表
export async function onRequest(context) {
  const { request } = context;

  const blocks = [
    { id: 'wool', name: '羊毛' },
    { id: 'concrete', name: '混凝土' },
    { id: 'glass', name: '玻璃' },
    { id: 'stone', name: '石头' },
    { id: 'wood', name: '木材' },
    { id: 'ore', name: '矿石' },
    { id: 'natural', name: '自然' },
    { id: 'plants', name: '植物' },
    { id: 'terracotta', name: '陶瓦' },
    { id: 'glazed_terracotta', name: '带釉陶瓦' },
    { id: 'concrete_powder', name: '混凝土粉末' },
    { id: 'carpet', name: '地毯' },
    { id: 'shulker_box', name: '潜影盒' },
    { id: 'bed', name: '床' },
    { id: 'banner', name: '旗帜' }
  ];

  return new Response(JSON.stringify(blocks), {
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}