// 所有方块颜色映射数据 (客户端版本)
const BLOCK_DATA = {
  wool: {
    name: "羊毛",
    colors: {
      "(20,21,25)": ["minecraft:black_wool", 0],
      "(233,236,239)": ["minecraft:white_wool", 0],
      "(160,39,34)": ["minecraft:red_wool", 0],
      "(103,117,53)": ["minecraft:green_wool", 0],
      "(53,57,157)": ["minecraft:blue_wool", 0],
      "(247,233,163)": ["minecraft:yellow_wool", 0],
      "(240,118,19)": ["minecraft:orange_wool", 0],
      "(121,42,172)": ["minecraft:purple_wool", 0],
      "(114,71,40)": ["minecraft:brown_wool", 0],
      "(62,68,71)": ["minecraft:gray_wool", 0],
      "(142,142,134)": ["minecraft:light_gray_wool", 0],
      "(21,137,145)": ["minecraft:cyan_wool", 0],
      "(189,69,180)": ["minecraft:magenta_wool", 0],
      "(84,109,27)": ["minecraft:lime_wool", 0],
      "(58,175,217)": ["minecraft:light_blue_wool", 0],
      "(216,129,152)": ["minecraft:pink_wool", 0]
    }
  },
  concrete: {
    name: "混凝土",
    colors: {
      "(20,21,25)": ["minecraft:black_concrete", 0],
      "(233,236,239)": ["minecraft:white_concrete", 0],
      "(160,39,34)": ["minecraft:red_concrete", 0],
      "(103,117,53)": ["minecraft:green_concrete", 0],
      "(53,57,157)": ["minecraft:blue_concrete", 0],
      "(247,233,163)": ["minecraft:yellow_concrete", 0],
      "(240,118,19)": ["minecraft:orange_concrete", 0],
      "(121,42,172)": ["minecraft:purple_concrete", 0],
      "(114,71,40)": ["minecraft:brown_concrete", 0],
      "(62,68,71)": ["minecraft:gray_concrete", 0],
      "(142,142,134)": ["minecraft:light_gray_concrete", 0],
      "(21,137,145)": ["minecraft:cyan_concrete", 0],
      "(189,69,180)": ["minecraft:magenta_concrete", 0],
      "(84,109,27)": ["minecraft:lime_concrete", 0],
      "(58,175,217)": ["minecraft:light_blue_concrete", 0],
      "(216,129,152)": ["minecraft:pink_concrete", 0]
    }
  },
  glass: {
    name: "染色玻璃",
    colors: {
      "(20,21,25)": ["minecraft:black_stained_glass", 0],
      "(233,236,239)": ["minecraft:white_stained_glass", 0],
      "(160,39,34)": ["minecraft:red_stained_glass", 0],
      "(103,117,53)": ["minecraft:green_stained_glass", 0],
      "(53,57,157)": ["minecraft:blue_stained_glass", 0],
      "(247,233,163)": ["minecraft:yellow_stained_glass", 0],
      "(240,118,19)": ["minecraft:orange_stained_glass", 0],
      "(121,42,172)": ["minecraft:purple_stained_glass", 0],
      "(114,71,40)": ["minecraft:brown_stained_glass", 0],
      "(62,68,71)": ["minecraft:gray_stained_glass", 0],
      "(142,142,134)": ["minecraft:light_gray_stained_glass", 0],
      "(21,137,145)": ["minecraft:cyan_stained_glass", 0],
      "(189,69,180)": ["minecraft:magenta_stained_glass", 0],
      "(84,109,27)": ["minecraft:lime_stained_glass", 0],
      "(58,175,217)": ["minecraft:light_blue_stained_glass", 0],
      "(216,129,152)": ["minecraft:pink_stained_glass", 0]
    }
  },
  stone: {
    name: "石材",
    colors: {
      "(20,21,25)": ["minecraft:blackstone", 0],
      "(85,85,85)": ["minecraft:stone", 0],
      "(112,112,112)": ["minecraft:cobblestone", 0],
      "(155,155,155)": ["minecraft:andesite", 0],
      "(132,135,134)": ["minecraft:diorite", 0],
      "(209,202,186)": ["minecraft:granite", 0],
      "(54,57,61)": ["minecraft:deepslate", 0],
      "(75,75,75)": ["minecraft:tuff", 0],
      "(119,119,119)": ["minecraft:calcite", 0],
      "(189,174,158)": ["minecraft:sandstone", 0],
      "(37,23,16)": ["minecraft:netherrack", 0],
      "(69,29,29)": ["minecraft:nether_bricks", 0],
      "(45,22,27)": ["minecraft:crimson_nylium", 0],
      "(22,26,31)": ["minecraft:warped_nylium", 0],
      "(128,128,128)": ["minecraft:gravel", 0],
      "(220,220,220)": ["minecraft:quartz_block", 0]
    }
  },
  wood: {
    name: "木材",
    colors: {
      "(59,37,16)": ["minecraft:oak_wood", 0],
      "(88,68,39)": ["minecraft:spruce_wood", 0],
      "(169,138,86)": ["minecraft:birch_wood", 0],
      "(106,80,49)": ["minecraft:jungle_wood", 0],
      "(45,23,15)": ["minecraft:dark_oak_wood", 0],
      "(173,94,93)": ["minecraft:acacia_wood", 0],
      "(58,43,36)": ["minecraft:mangrove_wood", 0],
      "(55,41,64)": ["minecraft:crimson_hyphae", 0],
      "(44,66,82)": ["minecraft:warped_hyphae", 0],
      "(216,203,141)": ["minecraft:stripped_oak_wood", 0],
      "(114,88,53)": ["minecraft:stripped_spruce_wood", 0],
      "(196,176,118)": ["minecraft:stripped_birch_wood", 0],
      "(167,133,81)": ["minecraft:stripped_jungle_wood", 0],
      "(65,50,30)": ["minecraft:stripped_dark_oak_wood", 0],
      "(169,91,51)": ["minecraft:stripped_acacia_wood", 0],
      "(193,103,107)": ["minecraft:stripped_mangrove_wood", 0]
    }
  },
  ore: {
    name: "矿石",
    colors: {
      "(73,91,36)": ["minecraft:coal_ore", 0],
      "(224,224,224)": ["minecraft:iron_ore", 0],
      "(240,240,150)": ["minecraft:gold_ore", 0],
      "(53,114,53)": ["minecraft:copper_ore", 0],
      "(79,142,65)": ["minecraft:emerald_ore", 0],
      "(115,115,115)": ["minecraft:lapis_ore", 0],
      "(227,212,209)": ["minecraft:diamond_ore", 0],
      "(255,252,245)": ["minecraft:quartz_ore", 0],
      "(54,57,61)": ["minecraft:deepslate_coal_ore", 0],
      "(75,75,75)": ["minecraft:deepslate_iron_ore", 0],
      "(102,102,76)": ["minecraft:deepslate_gold_ore", 0],
      "(79,112,79)": ["minecraft:deepslate_copper_ore", 0],
      "(85,142,71)": ["minecraft:deepslate_emerald_ore", 0],
      "(31,46,76)": ["minecraft:deepslate_lapis_ore", 0],
      "(92,92,92)": ["minecraft:deepslate_diamond_ore", 0]
    }
  },
  natural: {
    name: "自然方块",
    colors: {
      "(97,153,97)": ["minecraft:grass_block", 0],
      "(131,105,83)": ["minecraft:coarse_dirt", 0],
      "(86,58,43)": ["minecraft:podzol", 0],
      "(118,85,43)": ["minecraft:sand", 0],
      "(37,23,16)": ["minecraft:soul_sand", 0],
      "(28,28,28)": ["minecraft:obsidian", 0],
      "(151,109,77)": ["minecraft:mud", 0],
      "(112,112,180)": ["minecraft:ice", 0],
      "(160,160,255)": ["minecraft:packed_ice", 0],
      "(210,210,255)": ["minecraft:blue_ice", 0],
      "(255,255,255)": ["minecraft:snow_block", 0],
      "(150,150,150)": ["minecraft:mycelium", 0],
      "(102,117,49)": ["minecraft:moss_block", 0],
      "(30,30,30)": ["minecraft:bedrock", 0]
    }
  },
  plants: {
    name: "植物",
    colors: {
      "(0,124,0)": ["minecraft:oak_leaves", 0],
      "(97,153,97)": ["minecraft:spruce_leaves", 0],
      "(128,167,85)": ["minecraft:birch_leaves", 0],
      "(59,71,18)": ["minecraft:jungle_leaves", 0],
      "(38,66,28)": ["minecraft:dark_oak_leaves", 0],
      "(154,161,80)": ["minecraft:acacia_leaves", 0],
      "(82,121,44)": ["minecraft:mangrove_leaves", 0],
      "(89,174,89)": ["minecraft:grass", 0],
      "(93,182,93)": ["minecraft:fern", 0],
      "(0,100,0)": ["minecraft:vine", 0],
      "(150,150,150)": ["minecraft:dead_bush", 0],
      "(144,144,144)": ["minecraft:cactus", 0],
      "(210,125,44)": ["minecraft:pumpkin", 0],
      "(251,147,22)": ["minecraft:melon", 0],
      "(34,139,34)": ["minecraft:lily_pad", 0],
      "(75,75,75)": ["minecraft:brown_mushroom", 0],
      "(255,150,150)": ["minecraft:red_mushroom", 0]
    }
  },
  terracotta: {
    name: "陶瓦",
    colors: {
      "(20,21,25)": ["minecraft:black_terracotta", 0],
      "(233,236,239)": ["minecraft:white_terracotta", 0],
      "(160,39,34)": ["minecraft:red_terracotta", 0],
      "(103,117,53)": ["minecraft:green_terracotta", 0],
      "(53,57,157)": ["minecraft:blue_terracotta", 0],
      "(247,233,163)": ["minecraft:yellow_terracotta", 0],
      "(240,118,19)": ["minecraft:orange_terracotta", 0],
      "(121,42,172)": ["minecraft:purple_terracotta", 0],
      "(114,71,40)": ["minecraft:brown_terracotta", 0],
      "(62,68,71)": ["minecraft:gray_terracotta", 0],
      "(142,142,134)": ["minecraft:light_gray_terracotta", 0],
      "(21,137,145)": ["minecraft:cyan_terracotta", 0],
      "(189,69,180)": ["minecraft:magenta_terracotta", 0],
      "(84,109,27)": ["minecraft:lime_terracotta", 0],
      "(58,175,217)": ["minecraft:light_blue_terracotta", 0],
      "(216,129,152)": ["minecraft:pink_terracotta", 0]
    }
  },
  glazed_terracotta: {
    name: "带釉陶瓦",
    colors: {
      "(20,21,25)": ["minecraft:black_glazed_terracotta", 0],
      "(233,236,239)": ["minecraft:white_glazed_terracotta", 0],
      "(160,39,34)": ["minecraft:red_glazed_terracotta", 0],
      "(103,117,53)": ["minecraft:green_glazed_terracotta", 0],
      "(53,57,157)": ["minecraft:blue_glazed_terracotta", 0],
      "(247,233,163)": ["minecraft:yellow_glazed_terracotta", 0],
      "(240,118,19)": ["minecraft:orange_glazed_terracotta", 0],
      "(121,42,172)": ["minecraft:purple_glazed_terracotta", 0],
      "(114,71,40)": ["minecraft:brown_glazed_terracotta", 0],
      "(62,68,71)": ["minecraft:gray_glazed_terracotta", 0],
      "(142,142,134)": ["minecraft:light_gray_glazed_terracotta", 0],
      "(21,137,145)": ["minecraft:cyan_glazed_terracotta", 0],
      "(189,69,180)": ["minecraft:magenta_glazed_terracotta", 0],
      "(84,109,27)": ["minecraft:lime_glazed_terracotta", 0],
      "(58,175,217)": ["minecraft:light_blue_glazed_terracotta", 0],
      "(216,129,152)": ["minecraft:pink_glazed_terracotta", 0]
    }
  },
  concrete_powder: {
    name: "混凝土粉末",
    colors: {
      "(20,21,25)": ["minecraft:black_concrete_powder", 0],
      "(233,236,239)": ["minecraft:white_concrete_powder", 0],
      "(160,39,34)": ["minecraft:red_concrete_powder", 0],
      "(103,117,53)": ["minecraft:green_concrete_powder", 0],
      "(53,57,157)": ["minecraft:blue_concrete_powder", 0],
      "(247,233,163)": ["minecraft:yellow_concrete_powder", 0],
      "(240,118,19)": ["minecraft:orange_concrete_powder", 0],
      "(121,42,172)": ["minecraft:purple_concrete_powder", 0],
      "(114,71,40)": ["minecraft:brown_concrete_powder", 0],
      "(62,68,71)": ["minecraft:gray_concrete_powder", 0],
      "(142,142,134)": ["minecraft:light_gray_concrete_powder", 0],
      "(21,137,145)": ["minecraft:cyan_concrete_powder", 0],
      "(189,69,180)": ["minecraft:magenta_concrete_powder", 0],
      "(84,109,27)": ["minecraft:lime_concrete_powder", 0],
      "(58,175,217)": ["minecraft:light_blue_concrete_powder", 0],
      "(216,129,152)": ["minecraft:pink_concrete_powder", 0]
    }
  },
  carpet: {
    name: "地毯",
    colors: {
      "(20,21,25)": ["minecraft:black_carpet", 0],
      "(233,236,239)": ["minecraft:white_carpet", 0],
      "(160,39,34)": ["minecraft:red_carpet", 0],
      "(103,117,53)": ["minecraft:green_carpet", 0],
      "(53,57,157)": ["minecraft:blue_carpet", 0],
      "(247,233,163)": ["minecraft:yellow_carpet", 0],
      "(240,118,19)": ["minecraft:orange_carpet", 0],
      "(121,42,172)": ["minecraft:purple_carpet", 0],
      "(114,71,40)": ["minecraft:brown_carpet", 0],
      "(62,68,71)": ["minecraft:gray_carpet", 0],
      "(142,142,134)": ["minecraft:light_gray_carpet", 0],
      "(21,137,145)": ["minecraft:cyan_carpet", 0],
      "(189,69,180)": ["minecraft:magenta_carpet", 0],
      "(84,109,27)": ["minecraft:lime_carpet", 0],
      "(58,175,217)": ["minecraft:light_blue_carpet", 0],
      "(216,129,152)": ["minecraft:pink_carpet", 0]
    }
  },
  shulker_box: {
    name: "潜影盒",
    colors: {
      "(20,21,25)": ["minecraft:black_shulker_box", 0],
      "(233,236,239)": ["minecraft:white_shulker_box", 0],
      "(160,39,34)": ["minecraft:red_shulker_box", 0],
      "(103,117,53)": ["minecraft:green_shulker_box", 0],
      "(53,57,157)": ["minecraft:blue_shulker_box", 0],
      "(247,233,163)": ["minecraft:yellow_shulker_box", 0],
      "(240,118,19)": ["minecraft:orange_shulker_box", 0],
      "(121,42,172)": ["minecraft:purple_shulker_box", 0],
      "(114,71,40)": ["minecraft:brown_shulker_box", 0],
      "(62,68,71)": ["minecraft:gray_shulker_box", 0],
      "(142,142,134)": ["minecraft:light_gray_shulker_box", 0],
      "(21,137,145)": ["minecraft:cyan_shulker_box", 0],
      "(189,69,180)": ["minecraft:magenta_shulker_box", 0],
      "(84,109,27)": ["minecraft:lime_shulker_box", 0],
      "(58,175,217)": ["minecraft:light_blue_shulker_box", 0],
      "(216,129,152)": ["minecraft:pink_shulker_box", 0]
    }
  },
  bed: {
    name: "床",
    colors: {
      "(20,21,25)": ["minecraft:black_bed", 0],
      "(233,236,239)": ["minecraft:white_bed", 0],
      "(160,39,34)": ["minecraft:red_bed", 0],
      "(103,117,53)": ["minecraft:green_bed", 0],
      "(53,57,157)": ["minecraft:blue_bed", 0],
      "(247,233,163)": ["minecraft:yellow_bed", 0],
      "(240,118,19)": ["minecraft:orange_bed", 0],
      "(121,42,172)": ["minecraft:purple_bed", 0],
      "(114,71,40)": ["minecraft:brown_bed", 0],
      "(62,68,71)": ["minecraft:gray_bed", 0],
      "(142,142,134)": ["minecraft:light_gray_bed", 0],
      "(21,137,145)": ["minecraft:cyan_bed", 0],
      "(189,69,180)": ["minecraft:magenta_bed", 0],
      "(84,109,27)": ["minecraft:lime_bed", 0],
      "(58,175,217)": ["minecraft:light_blue_bed", 0],
      "(216,129,152)": ["minecraft:pink_bed", 0]
    }
  },
  banner: {
    name: "旗帜",
    colors: {
      "(20,21,25)": ["minecraft:black_banner", 0],
      "(233,236,239)": ["minecraft:white_banner", 0],
      "(160,39,34)": ["minecraft:red_banner", 0],
      "(103,117,53)": ["minecraft:green_banner", 0],
      "(53,57,157)": ["minecraft:blue_banner", 0],
      "(247,233,163)": ["minecraft:yellow_banner", 0],
      "(240,118,19)": ["minecraft:orange_banner", 0],
      "(121,42,172)": ["minecraft:purple_banner", 0],
      "(114,71,40)": ["minecraft:brown_banner", 0],
      "(62,68,71)": ["minecraft:gray_banner", 0],
      "(142,142,134)": ["minecraft:light_gray_banner", 0],
      "(21,137,145)": ["minecraft:cyan_banner", 0],
      "(189,69,180)": ["minecraft:magenta_banner", 0],
      "(84,109,27)": ["minecraft:lime_banner", 0],
      "(58,175,217)": ["minecraft:light_blue_banner", 0],
      "(216,129,152)": ["minecraft:pink_banner", 0]
    }
  }
};

export { BLOCK_DATA };
export const BLOCK_NAMES = Object.keys(BLOCK_DATA);
export const BLOCK_DISPLAY_NAMES = Object.fromEntries(
  Object.entries(BLOCK_DATA).map(([key, val]) => [key, val.name])
);