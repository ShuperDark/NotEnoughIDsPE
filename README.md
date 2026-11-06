# NotEnoughIDsPE

Minecraft Pocket Edition **0.16.2 (iOS / arm64)** 向けの MobileSubstrate Tweak です。
ブロックIDとアイテムIDの上限を広げ、ほかの Tweak から使える API を提供します。

| | バニラ | NotEnoughIDsPE |
|---|---|---|
| ブロックID | 0〜255（1 バイト） | **0〜65535**（16 ビット） |
| アイテムID | 0〜511（符号付き16ビット） | **0〜65535**（符号なし16ビット） |

Java 版の [NotEnoughIDs](https://github.com/fewizz/NotEnoughIDs) の考え方を参考にしています。
アイテムIDの拡張は [IDexpand](https://github.com/ShuperDark/IDexpand) をもとにしています。

> [!IMPORTANT]
> この Tweak 単体ではゲームに何も追加されません。ブロックやアイテムを追加するのは、下の API を使う別の Tweak です。
> 例として、テスト用 Tweak「NEIDTest」があります。ID 65535 のブロック、ID 65534 のアイテム、バニラのブロック（階段、チェスト、かまど、レッドストーン系など）の複製を追加します。

ブロックIDは、別の場所に本当のIDを保存する「代わりのブロック」方式ではなく、**ゲームが扱うブロックIDそのものを 16 ビットにしています**。作業の段階・調べたアドレス・決めたことは [ROADMAP.md](ROADMAP.md) にまとめてあります。

---

## 目次

- [動作環境](#動作環境)
- [ビルドとインストール](#ビルドとインストール)
- [仕組み](#仕組み)
- [API を使う準備](#api-を使う準備)
- [API リファレンス](#api-リファレンス)
- [使用例：ブロックを追加する](#使用例ブロックを追加する)
- [使用例：バニラのブロックを複製する](#使用例バニラのブロックを複製する)
- [使用例：地形生成に追加する](#使用例地形生成に追加する)
- [アイテムだけを追加する](#アイテムだけを追加する)
- [ほかの Tweak との互換性](#ほかの-tweak-との互換性)
- [ログとトラブルシューティング](#ログとトラブルシューティング)
- [開発の記録](#開発の記録)
- [クレジット](#クレジット)

---

## 動作環境

- Minecraft PE **0.16.2**（iOS 版、arm64）
  - アドレスを直接指定しているため、ほかのバージョンでは動きません。
- 脱獄済み端末と MobileSubstrate
- 動作確認：iPod touch / iOS 12.5.5

## ビルドとインストール

[Theos](https://theos.dev/) が必要です。

```sh
cd NotEnoughIDsPE
make package
```

`debs/com.darkshuper.notenoughidspe_<version>_iphoneos-arm.deb` ができるので、端末にインストールします。

---

## 仕組み

起動時に、ゲーム本体の命令を書き換えます（約 5,000 か所）。書き換える前に、すべての場所の命令が想定どおりかを確認します。想定と違う場所があれば、その段階（またはそのグループ）だけ書き換えずに、ログに理由を出します。

書き換えは 1 命令ずつではなく、まとめて書き込みます（1 命令ずつだと起動に 20 秒以上かかり、iOS に強制終了されるため）。

### アイテムID（0〜65535）

| 内容 | 方法 |
|---|---|
| アイテムの表を広げる | `Item::mItems`（`Item*[512]`）の代わりに 65536 個分の表を確保し、参照している 142 か所を新しい表を読むように書き換え |
| 上限チェック | `id < 0x200` のチェック 10 か所を `id < 0x10000` に |
| 符号なし化 | `Item::mId` を符号付きで読む 499 か所などを、符号なしで読む命令に（32768 以上が負の数にならないように） |
| 描画情報 | `ItemRenderer::mItemGraphics` も 65536 個分に |

IDの値そのものは 16 ビットのままなので、セーブデータと通信の形式は変わりません。

### ブロックID（0〜65535）

0.16.2 では、ブロックIDはあらゆる場所で 1 バイトです。次の順に 16 ビットにしています。

| 段階 | 内容 |
|---|---|
| ブロックの表 | `Block::mBlocks` と、ID で引く 6 つの表（`BlockGraphics::mBlocks`、光、固体、透明度、ティック）を 65536 個分に |
| `Block` の ID | `Block+8` の ID を 16 ビットに（読み取り約 3,100 か所） |
| チャンク | チャンクごとに上位バイトの配列（32 KB）を追加。読み書き・セーブ・読み込みに対応 |
| ブロックの取得・設置 | `BlockSource::getBlock`、ブロックを置く処理（`LevelChunk::setBlockAndData` とそのコールバック）を 16 ビットに |
| ブロックを調べる処理 | `getBlockAndData` / `getBlockID` の呼び出し元を 16 ビットに（解析で安全と判定した 313 か所、その後の解析で広げた約 200 か所、ほかのプレイヤーがブロックを壊したときのサーバーの処理）。手で確認した残りの 54 か所には、256 以上のブロックを「代わりのバニラブロック」（既定は石）として見せる。ほとんどはバニラの特定のブロック（レール、ドアなど）かどうかを比べるだけの処理 |
| ブロックを置く処理 | バニラのブロックのクラスが自分の ID を置く処理（`BlockSource::setBlockAndData` に `BlockID` を渡す 52 か所）、落下ブロック、作物、`/clone` など |
| 火 | 燃え移りやすさ・燃え尽きやすさの表を 16 ビットに（`NEID_setBlockFlammable`） |
| 描画 | チャンクの描画、テクスチャの選択、インベントリ・手持ちの描画、ブロックの色（`NEID_setBlockColor`。ワールド・インベントリ・手持ち・ドロップしたアイテム・破片）、描画の設定（きれい／速い・葉が透けるか）、描画用の明るさのキャッシュ |
| 音・パーティクル | 足音、置く・壊す音、壊したとき・掘っている途中・走ったときの破片 |
| アイテム | ブロックのアイテム（`BlockItem`）の名前・アイコン・設置、`ItemInstance` の `mBlock` |
| ピストン | 押す・引く途中のブロック（`MovingBlockEntity`）の ID・描画・セーブ |
| バニラのクラスの複製 | バニラのブロックのオブジェクトを複製して 256 以上に登録（`NEID_cloneBlock`）。形・当たり判定・置き方・成長などの処理はバニラのまま |
| ブロックエンティティ | チェスト・かまどなどの複製も中身を持てる（チャンクの読み込み時の復元を含む） |
| 状態の切り替え | 火のついたかまど、レッドストーンランプ・鉱石・トーチ、リピーター、コンパレーター、日照センサーの複製が、自分の複製どうしで切り替わる（`NEID_setBlockLitPair`） |
| Mob | エンダーマンが運ぶブロック、ゾンビが壊すドア、シルバーフィッシュが隠れるブロック、頭にかぶるカボチャ |
| 地形生成 | ブロックを指定するバニラの生成クラス 8 種類（鉱石・花・草・泉・ネザーの溶岩泉・岩の塊・砂などの円盤・湖）を 256 以上の ID で使える（`NEID_createFeature`）。バニラの木 13 種類を 256 以上の丸太と葉で作れる（`NEID_createTreeFeature`）。地上の世界とネザーのチャンクの生成に追加できる（`NEID_addFeature` / `NEID_addFeatureIn`） |
| 道具 | 256 以上のブロックを掘ったときの道具の耐久値（ツルハシ・オノ・シャベル・剣はそのブロック、ハサミなどは代わりのブロック＝複製元で判定） |
| トロッコ | トロッコに表示するブロック（`Minecart::setDisplayBlock`、セーブの `DisplayTile`）に 256 以上のブロックを使える。バニラの 0.16.2 では表示ブロックの取得がトロッコにないエンティティデータ（20 / 21）を読んでいて、独自の表示ブロックが表示も保存もされなかったバグも直した（16 / 17 を読む） |
| 通信 | ブロックの更新（`UpdateBlockPacket`）とチャンクの送信（`FullChunkDataPacket`）で上位バイトも送る |

**セーブデータ**

- 上位バイトは、チャンクの地形データとは別のキー（タグ `N`）に保存します。
- 上位バイトが全部 0 のチャンクには何も書きません。
- バニラはこのキーを無視するので、Tweak を外してもワールドは開けます（256 以上のブロックは下位バイトのブロックになります）。

**バニラのブロックへの影響**

- バニラのブロックは上位バイトが 0 なので、書き換えた場所でもバニラとまったく同じ値が読まれます。
- 動作が変わるのは、256 以上のブロックがある場所だけです。

---

## API を使う準備

API は C の関数（`extern "C"`）として公開しています。シンボル名は `NEID_` で始まります。

### 1. 依存関係を書く

API を使う Tweak の `control` に、NotEnoughIDsPE への依存を追加します。

```
Depends: mobilesubstrate (>= 0.9.5000), com.darkshuper.notenoughidspe
```

### 2. 関数を `dlsym` で取得する

実行時に `dlsym(RTLD_DEFAULT, ...)` で取得します。

> [!WARNING]
> Tweak は名前順に読み込まれるので、あなたの Tweak の `%ctor` の時点では、NotEnoughIDsPE がまだ読み込まれていないことがあります。`%ctor` ではなく、**使う直前**（`Block::initBlocks` などのフックの中）で取得してください。

```objc
#include <dlfcn.h>

struct Block; struct Item; struct BlockSource;
struct BlockPos { int x, y, z; };

#define NEID_FN(ret, name, args) static ret (*name) args
NEID_FN(int,      NEID_apiStage, (void));
NEID_FN(bool,     NEID_registerBlock16, (uint16_t id, Block* block, uint8_t graphicsFrom));
NEID_FN(bool,     NEID_setBlockTextures, (uint16_t id, const char* up, const char* down,
                                          const char* north, const char* south, const char* west, const char* east,
                                          uint8_t soundFrom));
NEID_FN(bool,     NEID_setBlockDestroyTime, (uint16_t id, float time));
NEID_FN(bool,     NEID_setBlockExplosionResistance, (uint16_t id, float resistance));
NEID_FN(bool,     NEID_setBlockFriction, (uint16_t id, float friction));
NEID_FN(bool,     NEID_setBlockCreativeCategory, (uint16_t id, int category));
NEID_FN(bool,     NEID_setBlockLight, (uint16_t id, int emission, int lightBlock));
NEID_FN(bool,     NEID_setBlockTicking, (uint16_t id, bool ticking));
NEID_FN(bool,     NEID_setBlockFallback, (uint16_t id, uint8_t vanillaId));               // ここから下は NEID_apiStage() >= 7
NEID_FN(bool,     NEID_setBlockFlammable, (uint16_t id, int flameOdds, int burnOdds));
NEID_FN(bool,     NEID_setBlockShape, (uint16_t id, int shape));
NEID_FN(Block*,   NEID_cloneBlock, (uint16_t id, uint8_t vanillaId, const char* name));
NEID_FN(bool,     NEID_setBlockLitPair, (uint16_t unlitId, uint16_t litId));
NEID_FN(bool,     NEID_setBlockColor, (uint16_t id, uint32_t rgb));
NEID_FN(void*,    NEID_createFeature, (int type, uint16_t id, uint8_t data, int param));
NEID_FN(void*,    NEID_createTreeFeature, (int kind, uint16_t logId, uint16_t leavesId));
NEID_FN(bool,     NEID_addFeature, (void* feature, int count, int minY, int maxY));
NEID_FN(bool,     NEID_addFeatureIn, (void* feature, int dimension, int count, int minY, int maxY));
NEID_FN(bool,     NEID_placeFeature, (void* feature, BlockSource* region, const BlockPos* pos, void* random));
NEID_FN(Block*,   NEID_getBlock16, (uint16_t id));
NEID_FN(Item*,    NEID_registerBlockItem16, (uint16_t blockId, const char* name));
NEID_FN(bool,     NEID_setBlock, (BlockSource* region, const BlockPos* pos, uint16_t id, uint8_t data, int flags));
NEID_FN(uint16_t, NEID_getBlockID, (BlockSource* region, const BlockPos* pos));

static bool loadNEID() {
	if (NEID_registerBlock16) return true;
	#define LOAD(name) name = (decltype(name))dlsym(RTLD_DEFAULT, #name)
	LOAD(NEID_apiStage); LOAD(NEID_registerBlock16); LOAD(NEID_setBlockTextures);
	LOAD(NEID_setBlockDestroyTime); LOAD(NEID_setBlockExplosionResistance); LOAD(NEID_setBlockFriction);
	LOAD(NEID_setBlockCreativeCategory); LOAD(NEID_setBlockLight); LOAD(NEID_setBlockTicking); LOAD(NEID_setBlockFallback);
	LOAD(NEID_setBlockFlammable); LOAD(NEID_setBlockShape); LOAD(NEID_cloneBlock); LOAD(NEID_setBlockLitPair);
	LOAD(NEID_setBlockColor); LOAD(NEID_createFeature); LOAD(NEID_addFeature); LOAD(NEID_placeFeature);
	LOAD(NEID_createTreeFeature); LOAD(NEID_addFeatureIn);
	LOAD(NEID_getBlock16); LOAD(NEID_registerBlockItem16); LOAD(NEID_setBlock); LOAD(NEID_getBlockID);
	#undef LOAD
	return NEID_registerBlock16 && NEID_apiStage && NEID_apiStage() >= 6;
}
```

---

## API リファレンス

すべての関数は、対応する段階の書き換えが成功していないと `false`（または `nullptr`）を返し、`NotEnoughIDsPE.log` に理由を書きます。

### `NEID_apiStage`

```c
int NEID_apiStage(void);
```

この版が実装しているブロックIDの段階を返します（この版は `7`）。この README の API は **6 以上**で使えます。`NEID_setBlockFallback` 以降の関数（`NEID_setBlockFlammable` / `NEID_setBlockShape` / `NEID_cloneBlock` / `NEID_setBlockLitPair` / `NEID_setBlockColor` / 地形生成の 5 つ）は **7 以上**です。

### `NEID_registerBlock16`

```c
bool NEID_registerBlock16(uint16_t id, Block* block, uint8_t graphicsFrom);
```

`Block` を ID `id`（**256〜65535**）に登録します。

| 引数 | 説明 |
|---|---|
| `id` | ブロックID。 |
| `block` | `Block::Block(name, id, material)` で、**同じ `id`** を渡して作った `Block`。 |
| `graphicsFrom` | 見た目を借りるバニラのブロックID。`NEID_setBlockTextures` で自分の見た目を設定するまで使われます（例: `3` = 土）。 |

- **呼ぶ時期:** `Block::initBlocks`（`0x1007D451C`）のフックの中で、元の関数を呼んだあと。
- **戻り値:** 次の場合は `false` です。
  - `id < 256`
  - `block` の ID（`Block+8`）が `id` と違う
  - その ID がすでに使われている

> [!NOTE]
> **`Block` の作り方**
> - `calloc` などで確保し（`sizeof(Block)` は 0xB0。少し大きめに確保すると安全です）、コンストラクタ `Block::Block(std::string const& name, int id, Material const&)`（`0x1007D7E20`）を直接呼びます。
> - ID には**本当の 16 ビットの ID** を渡します。コンストラクタは、光・固体・透明度の表に 16 ビットの ID で書き込みます。
> - `Block::registerBlock<>` テンプレートは使わないでください（`Block::mBlocks[id & 0xFF]` を上書きします）。
> - メモリは解放しないでください（ゲームが終わるまで使われます）。

### `NEID_setBlockTextures`

```c
bool NEID_setBlockTextures(uint16_t id, const char* up, const char* down,
                           const char* north, const char* south, const char* west, const char* east,
                           uint8_t soundFrom);
```

ブロックの見た目（`BlockGraphics`）を設定します。

| 引数 | 説明 |
|---|---|
| `up` 〜 `east` | 各面のテクスチャ名（地形アトラス `terrain_texture.json` の名前。例: `"stone"`, `"gold_block"`）。`north` は必須で、ほかを `nullptr` か `""` にすると `north` と同じになります。 |
| `soundFrom` | 音（置く・壊す・足音）をまねるバニラのブロックID。`0` なら変えません。 |

- **使われる場所:** ワールドの描画、インベントリ・手持ちの立方体、アイテムのアイコン、破片、音。
- **呼ぶ時期:** `NEID_registerBlock16` のあとならいつでも。
- **テクスチャの解決:** テクスチャ（アトラス）が読み込まれたあとで、自動的に行われます。リソースの読み込み直しにも対応しています。
- **破片のテクスチャ:** 壊したときの破片には**下の面**のテクスチャが使われます（バニラと同じです）。
- **形:** `NEID_registerBlock16` で作ったブロックは立方体です。`NEID_cloneBlock` で作った複製は、テクスチャを変えても**バニラの形のまま**です（例：階段の複製に金ブロックのテクスチャ）。

### `NEID_setBlockShape`

```c
bool NEID_setBlockShape(uint16_t id, int shape);
```

`NEID_setBlockTextures` で見た目を設定したブロックの、描画の形を変えます。`shape` は `BlockGraphics` の形の番号です（`0` が立方体で、番号はバニラの `BlockGraphics::initBlocks` と同じ）。

- 見た目だけが変わります。当たり判定や置き方はブロックのクラスのままです。形に合った処理が必要なら、`NEID_cloneBlock` でその形のバニラのブロックを複製してください。
- `NEID_setBlockTextures` の前に呼んでもかまいません（見た目を設定したときに反映されます）。リソースの読み込み直しにも対応しています。

### ブロックの性質

| 関数 | 内容 |
|---|---|
| `bool NEID_setBlockDestroyTime(uint16_t id, float time)` | 硬さ（土 0.5、石 1.5、黒曜石 50）。爆発への耐性も `time * 5` まで引き上げます（バニラの `setDestroyTime` と同じ）。 |
| `bool NEID_setBlockExplosionResistance(uint16_t id, float resistance)` | 爆発への耐性（バニラの `setExplodeable` と同じく、内部では 3 倍して保存）。 |
| `bool NEID_setBlockFriction(uint16_t id, float friction)` | 滑りやすさ（通常 0.6、氷 0.98）。 |
| `bool NEID_setBlockCreativeCategory(uint16_t id, int category)` | クリエイティブのタブ。`1` ブロック、`2` 装飾、`3` 道具、`4` アイテム、`0` 表示しない。**ブロックのアイテムは、ブロック側のこの値でタブが決まります。** |
| `bool NEID_setBlockLight(uint16_t id, int emission, int lightBlock)` | 光の強さ 0〜15（松明 14、グロウストーン 15）と、光を遮る量 0〜15（不透明 15、ガラス 0）。`-1` の引数は変えません。 |
| `bool NEID_setBlockTicking(uint16_t id, bool ticking)` | ランダムティック（`Block::randomTick`）を受けるか。 |
| `bool NEID_setBlockColor(uint16_t id, uint32_t rgb)` | ブロックの色 `0xRRGGBB`。草や葉と同じく、テクスチャの色に**掛け算**されます（白い部分はその色に、黄色に青を掛けると暗い緑になります）。ワールド・インベントリ・手持ち・ドロップしたアイテム・破片に効きます。256 以上だけ。 |
| `bool NEID_setBlockFlammable(uint16_t id, int flameOdds, int burnOdds)` | 火の燃え移りやすさ（バニラは 5〜60、`0` で燃えない）と、燃え尽きやすさ（5〜100）。バニラの `FireBlock::setFlammable` と同じ値です。既定は燃えません（複製は元のブロックと同じ値）。0〜255 を渡すとバニラのブロックの値を変えます。 |
| `bool NEID_setBlockFallback(uint16_t id, uint8_t vanillaId)` | 1 バイトのままのゲームの処理から見える**代わりのバニラブロック**（既定 `1` 石）。透けるブロックなら `20`（ガラス）など。`0`（空気）も指定できます。 |
| `Block* NEID_getBlock16(uint16_t id)` | その ID の `Block`（なければ `nullptr`）。0〜255 ならバニラのブロック。 |

### `NEID_cloneBlock`

```c
Block* NEID_cloneBlock(uint16_t id, uint8_t vanillaId, const char* name);
```

バニラのブロック `vanillaId` を複製して、ID `id`（**256〜65535**）に登録します。オブジェクトごと複製するので、そのブロックの**クラスの処理がすべてそのまま使えます**（形・当たり判定・置き方・成長・ブロックエンティティなど）。

| 引数 | 説明 |
|---|---|
| `id` | 新しいブロックID。 |
| `vanillaId` | 複製するバニラのブロックID（例：`53` オークの階段、`54` チェスト、`61` かまど）。 |
| `name` | 名前。名前のキーは `tile.<name>.name` になります。 |

- **呼ぶ時期:** `Block::initBlocks` のフックの中で、元の関数を呼んだあと（`NEID_registerBlock16` と同じ）。アイテムは、そのあと `NEID_registerBlockItem16` で作ります。
- **戻り値:** 作った `Block*`。次の場合は `nullptr` です。
  - `id < 256`、または `name` が空
  - その ID がすでに使われている
  - `vanillaId` のブロックがない
- **はじめから引き継ぐもの:** 見た目（`NEID_setBlockTextures` で変えられます）、光・固体・透明度・ティック、燃えやすさ、クリエイティブのタブ、代わりのブロック（`NEID_setBlockFallback` の既定が元のブロックになります）。
- **元のブロックとして扱われる場面:** ゲームが「このブロックは〇〇か」と調べる処理（`Block::isType` など）では、複製は元のブロックと同じに扱われます。例：レッドストーンワイヤーがつながる、シルバーフィッシュが仲間を起こす、カボチャの複製を頭にかぶれる。
- **ブロックエンティティ:** チェストやかまどの複製は、バニラと同じく中身を持ちます。ラージチェストも作れます。

> [!NOTE]
> **複製の注意点**
> - **状態で切り替わるブロック**（火のついたかまど、レッドストーンランプなど）は、バニラでは別の ID のブロックに置き換わります。複製どうしで切り替えるには、両方の状態を複製して `NEID_setBlockLitPair` で組にします。組にしないと、複製は今の状態のまま変わりません。
> - **2 ブロックの高さのブロック:** 植物（ヒマワリなど）の複製は、上半分も自分で置きます。ドアやベッドは、バニラでは専用のアイテム（`DoorItem` など）が両方の半分を置きます。`NEID_registerBlockItem16` のアイテムは普通の `BlockItem` なので、両方の半分は置かれないはずです（未確認。NEIDTest のドアの複製は、コードから `NEID_setBlock` で両方の半分を置いて確認しています）。
> - **種類ごとに名前を変えるブロック**（虫食いブロックなど）は、名前を自分の処理で決めます。複製でもバニラの名前（例：「Silverfish の石」）が表示されます。
> - **専用のアイテムで置くブロック**（リピーター、コンパレーターなど）は、バニラでもクリエイティブのタブが `0` です。複製もそれを引き継ぐので、表示するには `NEID_setBlockCreativeCategory` でタブを指定します。

### `NEID_setBlockLitPair`

```c
bool NEID_setBlockLitPair(uint16_t unlitId, uint16_t litId);
```

状態で切り替わるブロックの複製を組にします。`unlitId` は消えている・オフの状態、`litId` はついている・オンの状態です。

使える組（どちらも `NEID_cloneBlock` の複製）:

| オフ（`unlitId`） | オン（`litId`） |
|---|---|
| かまど `61` | 火のついたかまど `62` |
| レッドストーンランプ `123` | ついたランプ `124` |
| レッドストーン鉱石 `73` | 光る鉱石 `74` |
| 消えたレッドストーントーチ `75` | レッドストーントーチ `76` |
| リピーター `93` | オンのリピーター `94` |
| コンパレーター `149` | オンのコンパレーター `150` |
| 日照センサー `151` | 反転した日照センサー `178` |

- かまどの複製は、切り替わっても中身（ブロックエンティティ）がそのまま残ります。
- **戻り値:** どちらかのブロックがない、または両方とも 255 以下なら `false`。

### 地形生成：`NEID_createFeature` / `NEID_createTreeFeature` / `NEID_addFeature` / `NEID_addFeatureIn` / `NEID_placeFeature`

```c
void* NEID_createFeature(int type, uint16_t id, uint8_t data, int param);
void* NEID_createTreeFeature(int kind, uint16_t logId, uint16_t leavesId);
bool  NEID_addFeature(void* feature, int count, int minY, int maxY);
bool  NEID_addFeatureIn(void* feature, int dimension, int count, int minY, int maxY);
bool  NEID_placeFeature(void* feature, BlockSource* region, const BlockPos* pos, void* random);
```

バニラの生成クラス（`Feature`）を、256 以上のブロックで作って使います。

| `type` | クラス | 置くもの | `param` |
|---|---|---|---|
| `0` | `OreFeature` | 石の中の鉱脈 | 鉱脈の大きさ（バニラの石炭は 17、ダイヤは 8） |
| `1` | `FlowerFeature` | 草の上の花の群れ（そのブロックが置ける場所だけ） | 使わない |
| `2` | `TallGrassFeature` | 草の群れ | 使わない |
| `3` | `SpringFeature` | 石に囲まれた泉（液体のブロック） | 使わない |
| `4` | `HellSpringFeature` | ネザーの溶岩泉 | `1` なら石の中だけ |
| `5` | `BlockBlobFeature` | 地面の上の岩の塊 | 半径（`0` なら 1 ブロック程度） |
| `6` | `SandFeature` | 水の中の砂などの円盤 | 半径 |
| `7` | `LakeFeature` | 湖（液体のブロック） | 使わない |

- **`NEID_createFeature`:** 生成クラスを作ります。`data` は置くブロックのデータ値です。
  - 呼ぶ時期は、ブロックを登録したあと（`Block::initBlocks` のフックの中など）です。
  - 次の場合は `nullptr` を返します。
    - `id` のブロックがない
    - `type` が範囲外
  - 作ったものは解放しないでください。
- **`NEID_createTreeFeature`:** バニラの木を、丸太と葉を指定して作ります。`NEID_createFeature` と同じように `NEID_addFeature` などに渡せます。
  - `kind` は次のどれかです。

    | `kind` | 木 | `kind` | 木 |
    |---|---|---|---|
    | `0` | オーク | `7` | 大きなオーク |
    | `1` | シラカバ | `8` | 沼のオーク（ツタ付き） |
    | `2` | 背の高いシラカバ | `9` | ジャングル |
    | `3` | トウヒ | `10` | 大きなジャングル |
    | `4` | マツ | `11` | ダークオーク |
    | `5` | 大きなマツ | `12` | アカシア |
    | `6` | 大きなトウヒ | | |

  - 木が置く丸太（17 / 162）が `logId` に、葉（18 / 161）が `leavesId` に置き換わります。`0` ならバニラのままです。
  - データ値（木の種類・丸太の向き・葉の消える判定）はバニラの木のままです。そのため、丸太と葉はバニラの丸太・葉の複製（`NEID_cloneBlock` で 17 / 18、アカシアとダークオークは 162 / 161）にしてください。
  - ブロックがない、または `kind` が範囲外なら `nullptr` を返します。
- **`NEID_addFeature`:** 地上の世界のチャンクの生成に追加します。バニラの生成のあと（`BiomeDecorator::decorate` の最後）に置かれます。
  - `count`: 1 チャンクに試す回数です。マイナスにすると「`-count` チャンクに 1 回」になります（例：`-8`）。
  - `minY` / `maxY`: 高さの範囲 `[minY, maxY)` です。`minY` をマイナスにすると地表（その位置の一番上のブロックの上）になります。
  - チャンクごとに独自の乱数を使うので、バニラの地形・鉱石・花の配置は変わりません。
  - 新しく作られるチャンクだけに効きます。
- **`NEID_addFeatureIn`:** `NEID_addFeature` の、世界を選べる版です。`dimension` は `0` が地上の世界、`1` がネザーです。
  - ネザーでは、バニラのネザーの生成のあと（`HellRandomLevelSource::postProcess` の中）に置かれます。
  - ネザーには地表がないので、`minY` は `0` 以上にしてください（マイナスなら `false`）。
- **`NEID_placeFeature`:** 生成クラスを `pos` で 1 回動かします。自分で生成の処理をフックするときに使います。`random` はゲームの `Random`（例えば生成の処理に渡されたもの）です。

> [!NOTE]
> バニラの生成クラスはブロックを 1 バイトで持っています。NotEnoughIDsPE は、`NEID_createFeature` で作ったものを `NEID_placeFeature`（`NEID_addFeature` もこれを使います）で動かしている間だけ、そのブロックを 16 ビットで扱います。生成クラスの `place()` を直接呼ぶと、下位バイトのブロックが置かれます。

### `NEID_registerBlockItem16`

```c
Item* NEID_registerBlockItem16(uint16_t blockId, const char* name);
```

ブロックのアイテムを、バニラと同じく**ブロックと同じ ID** の `BlockItem` として作り、`Item::mItems` に入れます。

- **呼ぶ時期:** `Item::registerItems`（`0x100733348`）のフックの中で、元の関数を呼んだあと。
- **できること:**
  - インベントリ・手持ちで、ブロックの立方体として描かれます。
  - 名前はブロックの名前（`tile.〜`）になります。
  - タップすると、バニラの `BlockItem` と同じ手順で置かれます。
  - アイテムのデータ値（aux）が、置いたブロックのデータ値になります（バニラの花や羊毛のアイテムと同じ）。例：赤い花の複製で aux 1 のアイテムはヒスイランとして置かれます。
- **戻り値:** 作った `Item*`。その ID のアイテムがすでにあるときは `nullptr` です。
- **クリエイティブインベントリへの追加:** 自分で行います（[使用例](#使用例ブロックを追加する)）。

### `NEID_setBlock` / `NEID_getBlockID`

```c
bool     NEID_setBlock(BlockSource* region, const BlockPos* pos, uint16_t id, uint8_t data, int flags);
uint16_t NEID_getBlockID(BlockSource* region, const BlockPos* pos);
```

座標にブロックを置く／座標のブロックIDを調べます（0〜65535）。

- **`NEID_setBlock` の動作:**
  - ゲーム自身の `BlockSource::setBlockAndData` を通して置きます。そのため、置いたときの処理（`onPlace`、周囲への通知、描画の更新など）もバニラと同じように動きます。
  - `flags` は通常 `3` です。
- **`NEID_getBlockID` の範囲外:** ワールドの範囲外や、読み込まれていないチャンクでは `0` を返します。
- **`region` の例:** プレイヤーの `BlockSource` は `Player+176` にあります。

---

## 使用例：ブロックを追加する

ID 65535 のブロック（上は金、下は鉄、側面はダイヤモンドのテクスチャ、ガラスの音、石の硬さ、光るブロック）とそのアイテムを追加する例です。NEIDTest と同じ内容です。

```objc
#include "substrate.h"
#include <string>
#include <cstdlib>
#include <mach-o/dyld.h>
#include <dlfcn.h>
// ... 上の「API を使う準備」の宣言と loadNEID() ...

static const uint16_t kMyBlockId = 65535;

struct Material; struct ItemInstance;
static Block*   (*Block$Block)(Block*, std::string const&, int, const Material&);   // 0x1007D7E20
static const Material& (*Material$getMaterial)(int);                              // 0x1008C6E74
static void     (*Item$addCreativeItem)(const ItemInstance&);                     // 0x100745F10
static ItemInstance* (*ItemInstance$ItemInstance)(ItemInstance*, int, int, int);  // 0x100756C70

static Block* myBlock;
static Item*  myBlockItem;

// (1) ブロックを作って登録する
static void (*_Block$initBlocks)();
static void Block$initBlocks() {
	_Block$initBlocks();
	if (!loadNEID()) return;

	myBlock = (Block*)calloc(1, 0x200);                                   // sizeof(Block) は 0xB0
	Block$Block(myBlock, "my_block", kMyBlockId, Material$getMaterial(1 /* DIRT */));
	if (!NEID_registerBlock16(kMyBlockId, myBlock, 3 /* 見た目は土を借りる */)) { myBlock = nullptr; return; }

	NEID_setBlockTextures(kMyBlockId, "gold_block", "iron_block", "diamond_block", nullptr, nullptr, nullptr, 20 /* ガラスの音 */);
	NEID_setBlockDestroyTime(kMyBlockId, 1.5f);
	NEID_setBlockCreativeCategory(kMyBlockId, 1 /* ブロック */);
	NEID_setBlockLight(kMyBlockId, 15, 15);
}

// (2) ブロックのアイテムを作る
static void (*_Item$registerItems)();
static void Item$registerItems() {
	_Item$registerItems();
	if (myBlock) myBlockItem = NEID_registerBlockItem16(kMyBlockId, "my_block");
}

// (3) クリエイティブインベントリに追加する
static void (*_Item$initCreativeItems)();
static void Item$initCreativeItems() {
	_Item$initCreativeItems();
	if (!myBlockItem) return;
	alignas(16) uint8_t buf[0x80] = {};
	ItemInstance$ItemInstance((ItemInstance*)buf, kMyBlockId, 1, 0);
	Item$addCreativeItem(*(ItemInstance*)buf);
}

%ctor {
	intptr_t slide = _dyld_get_image_vmaddr_slide(0);
	Block$Block               = (decltype(Block$Block))(0x1007D7E20 + slide);
	Material$getMaterial      = (decltype(Material$getMaterial))(0x1008C6E74 + slide);
	Item$addCreativeItem      = (decltype(Item$addCreativeItem))(0x100745F10 + slide);
	ItemInstance$ItemInstance = (decltype(ItemInstance$ItemInstance))(0x100756C70 + slide);

	MSHookFunction((void*)(0x1007D451C + slide), (void*)&Block$initBlocks,       (void**)&_Block$initBlocks);
	MSHookFunction((void*)(0x100733348 + slide), (void*)&Item$registerItems,     (void**)&_Item$registerItems);
	MSHookFunction((void*)(0x100734D00 + slide), (void*)&Item$initCreativeItems, (void**)&_Item$initCreativeItems);
}
```

### コードから置く・調べる

```objc
BlockPos pos = { 10, 64, 10 };
NEID_setBlock(region, &pos, 65535, 0, 3);       // 置く
uint16_t id = NEID_getBlockID(region, &pos);    // 65535
Block* b = NEID_getBlock16(id);                 // myBlock
```

### 名前の翻訳

名前のキーは、ブロックとブロックのアイテムが `tile.<名前>.name`、アイテムが `item.<名前>.name` です。翻訳を用意していない場合は、キーがそのまま表示されます。

---

## 使用例：バニラのブロックを複製する

金ブロックのテクスチャのオークの階段（65533）と、かまどの複製（65530、火のついた状態 65529）を追加する例です。NEIDTest と同じ内容です。上の例の `Block::initBlocks` と `Item::registerItems` のフックの中に書きます。

```objc
// Block::initBlocks のフックの中（元の関数を呼んだあと）
Block* stairs = NEID_cloneBlock(65533, 53 /* oak_stairs */, "my_stairs");
if (stairs) NEID_setBlockTextures(65533, "gold_block", nullptr, "gold_block", nullptr, nullptr, nullptr, 0);   // 形は階段のまま

Block* furnace    = NEID_cloneBlock(65530, 61 /* furnace */,     "my_furnace");
Block* litFurnace = NEID_cloneBlock(65529, 62 /* lit_furnace */, "my_lit_furnace");
if (furnace && litFurnace) NEID_setBlockLitPair(65530, 65529);   // 燃えている間は 65529、止まると 65530

// Item::registerItems のフックの中（元の関数を呼んだあと）
NEID_registerBlockItem16(65533, "my_stairs");
NEID_registerBlockItem16(65530, "my_furnace");   // 火のついた状態にはアイテムを作らない（バニラと同じ）
```

---

## 使用例：地形生成に追加する

ID 65535 のブロックを鉱石として、ID 65511（花の複製）を花の群れとして、複製の丸太と葉で大きなオークを生成する例です。NEIDTest と同じ内容です。`Block::initBlocks` のフックの中で、ブロックを登録したあとに書きます。

```objc
void* ore = NEID_createFeature(0 /* OreFeature */, 65535, 0, 8);        // 大きさ 8 の鉱脈
if (ore) NEID_addFeature(ore, 10, 0, 64);                               // 1 チャンクに 10 回、Y 0〜63

NEID_cloneBlock(65511, 37 /* yellow_flower */, "blue_dandelion");
NEID_setBlockColor(65511, 0x3366FF);                                    // 青を掛ける
void* flower = NEID_createFeature(1 /* FlowerFeature */, 65511, 0, 0);
if (flower) NEID_addFeature(flower, 2, -1, 0);                          // 1 チャンクに 2 回、地表

NEID_cloneBlock(65510, 17 /* log */, "red_log");
NEID_cloneBlock(65509, 18 /* leaves */, "pink_leaves");
NEID_setBlockColor(65510, 0xFF5050);
NEID_setBlockColor(65509, 0xFF80E0);
void* tree = NEID_createTreeFeature(7 /* 大きなオーク */, 65510, 65509);
if (tree) NEID_addFeature(tree, -3, -1, 0);                             // 3 チャンクに 1 回、地表

void* netherOre = NEID_createFeature(0 /* OreFeature */, 65535, 0, 8);
if (netherOre) NEID_addFeatureIn(netherOre, 1 /* ネザー */, 8, 10, 118); // ネザーラックの中、Y 10〜117
```

---

## アイテムだけを追加する

普通のアイテムを追加するのに、専用の API は要りません。NotEnoughIDsPE が入っていれば、0〜65535 の任意の ID が使えます。

1. `Item` のコンストラクタ（`0x10074689C`）を `id - 256` で呼びます。`Item::mId` には `id` が入ります。
2. `Item::mItems` の**新しい表**（`((Item***)(0x1012AE238 + slide))[1]`）の `[id]` に入れます。

```objc
Item** items = ((Item***)(0x1012AE238 + slide))[1];      // 新しい表（65536 個）
Item* item = (Item*)calloc(1, 0x200);
Item$Item(item, "my_item", (short)(65534 - 256));
items[65534] = item;
*(int*)((uint8_t*)item + 112) = 4;                       // クリエイティブの分類: アイテム
// アイコンは Item::initClientData のフック内で Item::setIcon(item, "apple", 0)（0x100746B0C）など
```

> [!CAUTION]
> 元の `Item::mItems`（`0x1012AE238`、512 個分）には**直接書き込まないでください**。特に `mItems[1]` は新しい表へのポインタなので、上書きするとゲームが落ちます。

---

## ほかの Tweak との互換性

- **`Item::mItems` を使う Tweak**
  - `Item::mItems` に直接アクセスしている Tweak は、新しい表（`mItems[1]`）を使うように変更が必要です。
- **ゲーム本体の命令を書き換える Tweak**
  - NotEnoughIDsPE は約 5,000 か所の命令と、いくつかの関数を書き換えています。同じ場所を書き換える Tweak とは競合します。
  - 競合すると、命令の確認で「想定と違う」と判断され、その段階が無効になります（ログに出ます）。

---

## ログとトラブルシューティング

アプリの Documents フォルダの `NotEnoughIDsPE.log` に、起動時の結果が書かれます。正常な場合は、次のような行が出ます。

```
7a: zombie door break particles, silverfish wake-up, pumpkin copies: 16-bit
7a: falling-block drops, crop neighbours, /clone: 16-bit
7a: block-change listener 16-bit, falling blocks 16-bit
7a: path finder stand-in block
7a: Enderman carries 16-bit blocks: yes
7c: 13 raw chunk reads 16-bit, Block::isType knows copies, drops of copies own item
7d: world generation features 16-bit (19 sites)
7d: block color on items and particles on
7d: graphics mode (fancy / transparent leaves) sent to 16-bit blocks
7e: light emission in the render light cache 16-bit
7e: tool wear on 16-bit blocks 16-bit
7e: minecart display block 16-bit
self-check: tables 65536, block id 16-bit, 256 blocks, 0 id mismatches, 0 old-table mismatches, chunk +hi array
stage 4a: 18 store sites patched, 16-bit getBlock on; stage 4b: callbacks widened, 16-bit setBlock on; stage 5a: render 16-bit;
stage 5b: 76 id loads widened; stage 6: block items on, item drawing 16-bit; stage 4c: 286 caller groups widened, 0 skipped,
step sounds 16-bit; stage 4d: break effects 16-bit (6 senders), particle senders 4/4; stage 4e: 54/54 1-byte callers see
the fallback block; stage 4f: pistons 16-bit; stage 3d: network 16-bit, server break 16-bit; stage 7a: 161 groups
(124 + 83 xyz calls, 21 fire-odds reads) widened, 0 skipped; setBlock(BlockID): 52 calls in 44 groups widened, 0 skipped;
caves 4386/8192 insns
```

（実際のログでは `stage 4a:` から `insns` までが 1 行です。数は版によって変わります。）

| ログ | 意味 |
|---|---|
| `unexpected insn xxxxxxxx @ 1xxxxxxxx` | 書き換える予定の命令が想定と違っていました。ゲームのバージョンが 0.16.2 でないか、ほかの Tweak が同じ場所を書き換えています。その段階は無効になります。 |
| `... NOT patched` / `off` | その段階が無効になっています。直前の行に理由が出ます。 |
| `group N skipped` | 呼び出し元の 1 グループだけを飛ばしました（ほかはそのまま動きます）。 |
| `cave area too small` | 中継コードの領域が足りません（開発用のメッセージです）。 |
| `chunk vanilla` | チャンクの拡張が効いていません。上位バイトは保存されません。 |
| `stage 4e: N/M` | N が M より少ないときは、一部の呼び出し元が書き換えられていません（直前の行に `4e: site ... skipped`）。 |
| `7d: world generation features NOT patched` | 地形生成の書き換えが効いていません。`NEID_createFeature` などは `false` / `nullptr` を返します。 |
| `7d: block color on items and particles NOT patched` | ブロックの色がワールドでしか効きません（インベントリ・手持ち・破片は元の色）。 |
| `7e: ... NOT patched` | 光るブロックの描画の明るさ・道具の耐久値・トロッコの表示ブロックのどれかが、1 バイトの ID のままです。 |
| `cloneBlock(N): ...` | `NEID_cloneBlock` の結果です。`already taken`（ID が使用済み）、`no vanilla block`（`vanillaId` がない）など。 |
| `server break fallback` | ほかのプレイヤーが壊したときのサーバーの処理が 16 ビットになっていません。壊したときの破片・音・ドロップが代わりのブロック（既定は石）のものになります。 |

---

## 開発の記録

**作成時間**
- 期間: 2026-11-01 〜 2026-11-06（6 日間）
- 作業時間: 約 21 時間（Claude Code との会話の記録から、30 分以上の空きを除いて計算。実機での確認の時間も、その間に含まれる分だけ入っています）
- 内訳: 11/01 約 8 時間、11/02 約 2.5 時間、11/03 約 4 時間、11/04 約 4 時間、11/05 約 2.5 時間、11/06 約 0.5 時間

**Claude Code から見て大変だったこと**
- **iOS 版に関数名がないこと。** iOS 版の実行ファイルには記号がないので、記号のある Android 版（32 ビット ARM）で関数の意味を調べ、iOS 版（arm64）の同じ処理を命令の並びや文字列から探しました。構造体の大きさや vtable の番号は 2 つの版で違うので、毎回照らし合わせが必要でした。
- **1 バイトの ID が至るところにあること。** `Block+8` の ID を読む命令だけで 3,000 か所以上あります。`LDRB [Xn,#8]` は Block 以外の構造体でもよく使われる形なので、制御フローをたどって「この `Xn` は本当に Block か」を判定するスクリプトを作りました。BlockGraphics も +8 に 1 バイトの ID を持っていて、そこを Block と間違えて 2 バイトで読んだときは、壊したときにクラッシュしました。
- **広げられない 1 バイトの受け渡し。** スタック上の 1 バイトの `FullBlock` や `BlockID` は、隣の変数とぶつかるので簡単には広げられません。広げられる場所は解析で選んで 16 ビットにし、残りは「代わりのバニラブロック」を見せる、という二段構えにしました。
- **自分でゲームを動かせないこと。** 確認はすべて、実機で試していただいたログと説明が頼りでした。原因を絞れるように、ログに出す内容を毎回考えました。
- **バニラ自身のバグ。** エンダーマンがカボチャをかぶっていても怒る件や、トロッコの表示ブロックが 0.16.2 では元から動かない件は、最初は NotEnoughIDsPE の不具合に見えました。バニラのバグだと確かめるまで時間がかかりました。
- **命令の細かい違い。** IDA で同じ `MOV Wd, #imm` と表示される命令が 2 種類の書き方（`MOVZ` と `ORR`）を持つことなど、書き換える前の命令の照合で何度かつまずきました。

---

## クレジット

- [NotEnoughIDs](https://github.com/fewizz/NotEnoughIDs)：ブロックIDを広げる考え方の参考
- [IDexpand](https://github.com/ShuperDark/IDexpand)：アイテムの表の移動の元になった実装
