# ブロックID 16 ビット化の計画と調査メモ

BlockExtraData を使わずに、ブロックIDそのものを 16 ビット（0〜65535）にするための作業計画です。
対象は MCPE 0.16.2 iOS（arm64）。アドレスはすべてスライド前です。

## 段階

| 段階 | 内容 | 状態 |
|---|---|---|
| 1 | ブロックIDで引く表 7 つを 65536 個に広げる（576 か所の `ADRP+ADD` → `LDR`） | 完了・実機確認済み |
| 2 | `Block+8` の ID を 16 ビットに（コンストラクタの `STRB`→`STRH`、ID 読み取り 3,082 か所 `LDRB`→`LDRH`） | 完了・実機確認済み |
| 3a | `LevelChunk` を 32,784 バイト大きく確保し、上位バイト配列（+87120）とフラグ（+119888）を用意 | 完了・実機確認済み |
| 3b | チャンクの書き込み・読み取り関数を上位バイト対応にする（段階 4 と一緒に進める） | 完了（4a・4b で対応、実機確認済み） |
| 3c | セーブ（LevelDB）と読み込みに上位バイトを追加（タグ `N` の別キー、形式 1） | 完了・実機確認済み |
| 3d | 通信。`UpdateBlockPacket`（0x17、+0x1F の詰め物に上位バイト、ID は varint で 16 ビットのまま送る）: write `0x1004AE504` / read `0x1004AE570`、送り手 4 か所（`0x10051FF54` / `0x10051FFF0` は 4c で 16 ビット化済みの ID、`0x10051F1BC` / `0x1008545EC` は位置から引き直す）、クライアントの設置 `0x100332BC0` → `neid_ubpSet`。チャンク（`0x10053D040`）: ブロックエンティティの後ろに NBT `{id:"NEIDHighBytes", d:<版 1, 1 疎 / 2 全部>}`。クライアントは `0x100334490` で上位バイトを消してから読み、`loadStatic` 呼び出し `0x10084AC00` でタグを受け取る（バニラは知らない ID として読み飛ばす）。ほかのプレイヤーの破壊（`RemoveBlockPacket` の処理 `0x10051EFF4`）は 4e の代わりのブロックをやめて 16 ビット化（Block・ドロップ・イベント 2001） | 完了・実機確認済み |
| 4a | `BlockSource::getBlock`（2 種）を 16 ビットで読む。ブロックを 1 個ずつ書く 18 か所で上位バイトを 0 にする（中継コード） | 完了・実機確認済み |
| 4b | ブロック設置の流れを 16 ビットに（`LevelChunk::setBlockAndData` を C++ で置き換え、コールバック 3 関数の BlockID 読み取り 15 か所を 2 バイトに）。`NEID_registerBlock16` / `NEID_setBlock` | 完了・実機確認済み |
| 5a | チャンク描画（`RenderChunkBuilder::_tessellateQueues`）が 16 ビット ID でブロックを選ぶ（`getBlockAndData` を 3 バイト形式の自前関数に差し替え） | 完了・実機確認済み（5b と一緒に確認） |
| 5b | 段階 2 で漏れた `LDRB [Xn,#8]` のうち、値がブロックID の表の添字にしか使われない 76 か所を `LDRH` に（描画のテクスチャ選択など。`tools/use_sites.py`）。BlockGraphics も +8 に 1 バイトの ID を持つ（+9 は別）ので、BlockGraphics の表から取ったものは除く（`0x100354C48` で破壊時にクラッシュした） | 完了・実機確認済み |
| 6a | ブロックアイテム（`NEID_registerBlockItem16`）。`Item+0x6E` の 1 バイトを読む 8 か所を中継コードで「アイテムID → 16 ビットのブロックID」表に。`BlockItem::useOn` で上位バイトを予約。ItemInstance の `mBlock` を作る 18 関数すべて | 完了・実機確認済み |
| 6b | インベントリ・手持ちの描画（`renderGuiItemInChunk` / `rebuildItem` → `renderGuiBlock` / `getMeshForBlock` / `appendTessellatedBlock`）。描いている間だけ 16 ビット ID をスレッドローカルに記録（C 関数を呼ぶ中継コード） | 完了・実機確認済み |
| 4c | `getBlockAndData` / `getBlockID` の呼び出し元のうち、`tools/c4.py` が安全と判定した 203 グループ（呼び出し 210 か所）。`BFI`/`BFXIL`/`MOVK` は書き込み先も読むので、ID に差し込む使い方は除外（初版で 4 グループ見逃していた）。`Level::destroyBlock` と描画の 1 か所は 4d / 5a で扱うを 3 バイト / 2 バイト形式に。残り（アドレスが関数に渡る、スロットの使い回し、ID を関数に渡すなど）は次の段階 | 完了・実機確認済み |
| 4c-3 | `tools/c4.py` の誤判定を修正して対象を拡大: 286 グループ（呼び出し 313 か所）。① `LDP` の 2 つ目の書き込み先を「読み取り」と数えていた ② 書き込み先より手前から始まるアドレスの受け渡しは安全（手前の変数が 3 バイト目に届くなら 1〜2 バイト目にもかかり、バニラ自身の読み取りと矛盾する）。残り約 180 か所（スロットの使い回し・自分のアドレスの受け渡し・ID の引数渡し・その他の使い道） | 完了・実機確認済み |
| 4c-2 | 足音: `Entity::move` → `_playMovementSound` → `_playStepSound`（ID を int で受け渡し）→ レベルサウンドイベント → `LevelRenderer::levelSoundEvent` の「data > 0xFF なら音の種類 15」を 16 ビット対応に。設置音（`BlockItem::useOn` `0x1007289AC`）も | 完了・実機確認済み |
| 4d | 破壊パーティクル・破壊音: イベント 2001 のデータのビット 16-31 に 16 ビット ID を入れる（送り手 6 か所 + `Level::destroyBlock`。下位バイトはそのまま）。受け手 `LevelRenderer::levelEvent`（`0x100405D7C`〜`0x100405DA8`）で記録 → `_destroyEffect` → `TerrainParticle::init`（`0x100354BBC`）。`Level::destroyBlock` のドロップも 16 ビットの Block で | 完了・実機確認済み |
| 4 | ブロックIDの受け渡しを 16 ビット化（残り）。4a〜4f と 7a〜7a-6 に分けて進めた | 完了（4a〜4f・7a） |
| 5 | 描画の残り（隣接ブロックのキャッシュ）・ライティング・地形生成。描画は 5a・5b・6b・7d・7e、光は 6d・7e、地形生成は 7d で対応 | 完了 |
| 6c | 見た目の登録 `NEID_setBlockTextures(id, 上, 下, 北, 南, 西, 東, 音をまねるブロック)`。`BlockGraphics` をバニラの名前で作り（コンストラクタが名前で Block を引き、null 確認がない）、+0x10 / +8 を自分のブロックに。`setTextureItem`（`0x1003829C8`）がその場でアトラスから UV を解決するので、`Item::initClientData` のフック（アトラス再読み込みのたび）で呼び直す。所有リストに入れないので teardown で消えない | 完了・実機確認済み |
| 4d-2 | 掘っている途中・走ったとき・着地などの破片（`Level::addParticle(0x12, ..., id \| data << 8)` の送り手 4 か所）。3 バイト形式にして `BFI` のあとでビット 16-31 に 16 ビット ID | 完了・実機確認済み |
| 6d | ブロックの性質 API（`NEID_setBlockDestroyTime` / `ExplosionResistance` / `Friction` / `CreativeCategory` / `Light` / `Ticking`、`NEID_getBlock16`）。バニラの setter は表を 1 バイトの ID で引くので、同じ書き込みを 16 ビットで直接行う（`Block+0x88` 硬さ、`+0x8C` 爆発耐性、`+0x80` 摩擦、`+0x90` 分類）。README を新方式で書き直し | 実機確認済み（光15・硬さ・タブ） |
| 4e | 4c で 16 ビットにできなかった `getBlockAndData` / `getBlockID` の呼び出し 171 か所（`tools/fb_sites.py`、末尾呼び出し `0x100572250` の `B` を含む）を、元の形式のまま「代わりのバニラ ID」（`gFallbackId[id]`、既定 1 = 石、`NEID_setBlockFallback`）を返す関数に向ける。`LevelChunk::setBlockAndData` は、`NEID_setBlock` を通らない書き込みで、256 以上のブロックがある場所に代わりの ID か下位バイト（0 以外）が書かれたら ID を保つ（読み → データ変更 → 書き戻し）。`NEID_apiStage` = 7。初版は `fb_sites.py` が 2 種類の印を逆にしていて 0/171（全部スキップ）だった | 実機確認済み（水・火・松明・レッドストーン） |
| 4f | ピストン: `MovingBlockEntity`（+0x61 ID / +0x62 データ）の詰め物 +0x63 に上位バイト。`_spawnMovingBlocks` の `setBlock` 呼び出し `0x1008409A8` → `neid_mbeSetBlock`（元の位置の 16 ビット ID を直接読む）、着地の `BlockSource::setBlockAndData` 2 か所（`0x100840CE8` / `0x10083E63C`）→ `neid_mbeLand`（`NEID_setBlock` と同じ保留の上位バイト）、`Block::mBlocks` を引く読み取り 3 か所と描画（`0x1003AD6E4`、6b の描画メモ、`0x1003AD964` で解除。動いているブロックのメッシュ `0x1003A4584` が `Block::mBlocks[id]` を引く読み取りも 6b の読み取りサイトに追加）を 16 ビットに。コンストラクタ `0x10083D6AC` で +0x63 を 0、load/save（`0x10083D7EC` / `0x10083DA3C`）でタグ `neidMovingBlockIdHi` | 実機確認済み（押す・引く・動いている途中の描画） |
| 7a | 4e の呼び出し元を 16 ビットに（`tools/c7.py`）。4c との違い: 呼び出しから到達できるアクセスだけを見る（スタックの使い回しを許す）、IDA の `var_XX+N` の加算を考慮、データ値の書き戻し（`STRB` を 1 バイト後ろへ）、スロットのアドレスを `FullBlock::getBlock`（`0x100057C94`）・フラグ判定（`0x100057C5C`）・`BlockSource::setBlockAndData(pos, FullBlock const&, flags)`（`0x10079B320`）に渡す形（3 バイト版に差し替え）、ID を比較・16 ビットの表にしか使わない関数（`0x1007D2270` など）に渡す形を許す。`MOV X8, SP` のスロットも対象。`getBlockID(x,y,z)`（`0x10079C2D0`）/ `getBlockAndData(x,y,z)`（`0x10079E818`）の呼び出し元（4c の対象外で、全部が代わりのブロックを見ていた）も対象。第 1 弾: 4e の 170 か所のうち 79 か所 + (x,y,z) 版 83 か所（146 グループ）。第 2 弾: 火の燃えやすさ（`FireBlock+0xCC` / `+0x4CC` の `int[256]`）を 65536 個の表に（`ADD Xd, Xfire, Xid, LSL#2` / `LDR Wt, [X21, Xid, LSL#2]` を中継コードで、ID が 256 以上なら自前の表。`NEID_setBlockFlammable`）、戻り値で上書きされるスロット（`0x1008ED374` などの x8）、ID のアドレスを受け取る `0x100861C3C`（呼び出し元 2 か所と一緒に `LDRH`）。計 160 グループ・206 呼び出し（4e の表 123 + (x,y,z) 版 83）。残り 55 | 第 1 弾・第 2 弾とも実機確認済み（現在 161 グループ、スキップ 0、火の燃え移り・燃え尽きを確認） |
| 7a-3 | `BlockSource::setBlockAndData(pos, BlockID const&, data, flags)`（`0x10079BB6C`）の呼び出し元 59 か所（バニラのブロッククラスが自分の ID `this->id` を置く処理など）。`STRB` で 1 バイトのスロットに書いて渡していたのを `STRH` にし、呼び出しを 2 バイトを読む `neid_setBlockAndDataId16` に（`tools/c8.py`、`kSetId7Sites`）。段階 2 で Block と証明できなかった `LDRB [this,#8]` 11 か所も `LDRH` に（上位バイトは登録済みの ID のときだけ使うので安全）。52 か所・44 グループ。残り 7 か所は getBlockID の書き戻し（4b の規則で対応済み）など。`0x100388C7C`（`id << 3` で表を引く）も手で 7a に追加 | 実機確認済み（2026-11-03、複製の階段・ヒマワリなどが自分の ID で置ける） |
| 7a-4 | 4e に残った 54 か所を手で確認（`c7_rejects.json`）。ほとんどは ID をバニラのブロックと比べるだけ（レール・ドア・ポータル・作物・経路探索・地形生成・コマンドなど）で、複製は代わりのブロック＝複製元に見えるので正しく動く。ID を保存・受け渡すのはエンダーマンだけ: 持ち上げ `0x1006FF984`（`tLastXyz16`）、設置 `0x1006FF6B0`（保留の上位バイト）、「持っているか」`0x1006FF4E4` / `0x1006FF810`（`#0xFF` → `#0xFFFF`）、描画 `0x1003BA184` / `0x1003BA380` / メッシュ `0x1003BA534`〜`0x1003BA540`（6b の描画メモ）。セーブ `0x1006FEBA8`・ロード `0x1006FED14` の `#0xFF` も `#0xFFFF`。`mayPlace` の「ID が空気以下なら不可」`0x10079B15C` を 16 ビットに（下位バイト 0 の ID）。描画更新のリスナー `LevelRenderer::onBlockChanged`（`0x1003FBD28` など 4 か所、直前の変更を `tChgPos` / `tChgOld` / `tChgNew` に記録）。落下ブロック: エンティティデータ 2 の int の 3 バイト目に上位バイト（`_startFalling` `0x100809598` / `init` `0x1006F9448`、毎ティック `0x1006F8F64` / `0x1006F9220`、描画 `0x1003C3380`〜`0x1003C34BC`、セーブ・ロードに `neidTileHi`）。着地して自分を置く `Block::tryToPlace`（`0x1007D987C`）は保留の上位バイトで。`_placeCallbacks` の光の判定後の読み直し `0x100846DC4` も `LDRH`（下位バイト 0 だと `onPlace` が呼ばれなかった）。経路探索 `0x1008D04E8` はノード判定に代わりのブロックを渡す（複製の上でモブが回っていた）。残す: 作物の隣接判定 `0x1008237F4`（複製の作物同士は同じ作物と見なされず成長が少し遅い）、コマンドの `/clone` 系（`0x100580244` など） | 実機確認済み（エンダーマンの持ち上げ・設置・セーブ、下位バイト 0 の ID の設置・破壊・落下、複製の上のモブの移動） |
| 7a-5 | 7a-4 で残した小さなもの。着地できない落下ブロックのアイテム化（`0x1006F92B8` で 16 ビット ID をメモ、`Entity::spawnAtLocation(FullBlock const&)` の ID 読み込み `0x100660144` が使う）。作物の成長速度の「隣に同じ作物」（`this->id` `0x10082392C` を `LDRH`、代わりのブロックを見ていた隣 `0x100823938` は直前の読み込みの 16 ビット ID `tLastFb16`）。`/clone`（`CloneCommand::execute` `0x10058530C` をフックし、コピー元の読み込み直後 `0x100585C70` でコピー先の位置と 16 ビット ID を記録、チャンクのフックで戻す） | 実機確認済み（2026-11-04、/clone はバニラと複製の混在・再読み込み後も OK） |
| 7a-6 | Mob の処理の確認（シルバーフィッシュ、村人の収穫・植え付け・拾う・繁殖、ゾンビのドア破壊・拾う・装備）。村人とゾンビのアイテムはポインタか 16 ビットのアイテム ID の比較で対応済み（拾うのは村人だけ）。直したもの：ゾンビがドアを壊すイベント 2001 に 16 ビット ID（`0x1006B20B4`、4d と同じ）、虫食いブロックの複製も仲間を起こす（`0x1007051EC` `neid_familyId`）、カボチャの複製を頭にかぶれる・頭の描画（`neid_isPumpkin`：`0x1007598D4` `0x10032605C` `0x1003C8DB4`）、`enderman_look_for_player` の判定（`0x1006FF124` をフック）。バニラのエンダーマン（`enderman.json` の `minecraft:lookat`）は `other_without_armor` がデータ値 -1 を一致扱いしないバニラのバグ（`0x10064EBB4`）でカボチャが効かず、複製も同じ動き（直さない） | 実機確認済み |
| 7b | バニラのブロッククラスを 16 ビット ID で使う: `NEID_cloneBlock(id, vanillaId, name)`（バニラのブロックのオブジェクトを `malloc_size` の大きさで複製し、文字列 2 つ（+0x10 / +0x28）を作り直し、ID ごとの表・燃えやすさ・代わりのブロックもバニラと同じに）。独自テクスチャの BlockGraphics は `graphicsFrom` の +0x18..+0x3F（形 +0x20 など）を引き継ぐ。`NEID_setBlockShape(id, shape)`。テスト: 階段（65533）、ヒマワリ（65532、上半分を自分で置く） | 実機確認済み（2026-11-03、階段・ヒマワリの複製がバニラと同じ動き） |
| 7c | ブロックエンティティ。生成（`0x1008467BC` → `0x1008036A0` → `BlockEntityFactory` `0x10082F3D8`）は `Block+0x4C` の種類だけを見るので 4b のままで動く。直したもの: チャンク読み込み時のブロックエンティティ復元 `0x10084AC34`（下位バイトのブロックで判定していたので複製チェストの中身が消えていた。上位バイトの読み込みを `LevelChunk::deserialize` の前に移動）、チャンクのブロック配列を直接読む残り 12 か所（読み込み時の全ブロック処理 `0x10084C920`、ランダムティック `0x100849338`、高さマップ・空の光 `0x100846FB0` など、高さ検索 `0x10084BD74` など。`neid_chunkId16`）、`Block::isType`（`0x1007D8150`、ポインタ比較、呼び出し元 176 か所）は複製を複製元と同じ種類として扱う（中継コード、ポインタが同じなら従来どおり即 true）、`FurnaceBlock::setLit`（`0x100807D94`）は 16 ビットのかまどを `NEID_setBlockLitPair` の組で切り替える（`mNoDrop` `0x1012D2EE8` を立てて中身を保つ） 。ドロップ: `Block::spawnResources`（`0x1007D8B0C`）とその上書き（`0x10080D6FC`）で `getResource`（vfunc +0x1A0）の結果が複製元（または点火・消火の相手の複製元）のバニラ ID なら複製自身のアイテムに（`neid_dropId`） | 実機確認済み（複製チェスト・ラージチェスト・再読み込み・複製かまどの点火と消火）、複製のドロップ |
| 7c-2 | 状態で自分を置き換えるブロック（ランプ 123/124、レッドストーン鉱石 73/74、日照センサー 151/178、レッドストーントーチ 75/76、リピーター 93/94、コンパレーター 149/150、かまど 61/62）。`neid_LevelChunk_setBlockAndData` で、複製が複製元の相手のバニラ ID に置き換えられるときは `NEID_setBlockLitPair` の複製の相手に（組がなければ複製のまま、`kVanillaStatePairs`）。ドロップ: アイテムで置くブロック（リピーター 356→93、コンパレーター 404→149、ドアなど `kItemPlacesBlock`）の複製は複製自身のアイテムを落とす。予約ティック（`BlockTickingQueue::tickPendingTicks` `0x1007A0318` / `0x1007A0320`）はその位置の 16 ビット ID と、予約のバイトが下位バイトか代わりのブロックなら一致とみなす。日照センサーのブロックエンティティ（`0x100836FF0`）とレッドストーンダストの接続判定（`0x10081B714`）は複製を複製元として扱う | 実機確認済み（ランプ・鉱石・日照センサー・トーチ・リピーター・コンパレーター、ダストの繋がり） |
| 7d | 地形生成: ブロックを引数に取るバニラの生成クラス 8 つ（`BlockBlobFeature` / `FlowerFeature` / `HellSpringFeature` / `LakeFeature` / `OreFeature` / `SandFeature` / `SpringFeature` / `TallGrassFeature`、iOS では Feature+13 に 1 バイトの BlockID、+14 にデータ値か 2 つ目のブロック）を 16 ビット ID で使えるように。`NEID_createFeature` が下位バイトで作り 16 ビット ID を `gFeatureIds` に記録、`NEID_placeFeature` の間（スレッドローカル `tFeat*`）だけ place() 内の +13 読み取り 19 か所が中継コードで 16 ビットに（置く: `tPending*` に一度だけ、`Block::mBlocks` の添字・比較: 16 ビット ID）。`NEID_addFeature` は `BiomeDecorator::decorate`（`0x1007C6514`）のフックでバニラの後に置く（チャンクごとの独自の乱数、バニラの乱数は変えない）。中継コードの領域を 8192 命令に。あわせて: 交差した形（花・苗木）など描画の `BlockGraphics::mBlocks[id]` の取りこぼし 4 か所（`0x100390EEC` / `0x1003910DC` / `0x1003A3A44` / `0x1003A3A98`）を `LDRH` に、`NEID_setBlockColor`（Block の vtable を複製して 83〜85 の `getColor` を差し替え）、NEID のブロックアイテムは aux をデータ値として置く（Item vtable 17 `getLevelDataForAuxValue`）・ドロップしたアイテムの色（Item vtable 35 `getColor`）。続けて: 木（`NEID_createTreeFeature`、バニラの木 13 種類を `BiomeDecorator::BiomeDecorator` と同じ引数で作り、`NEID_placeFeature` の間だけ `LevelChunk::setBlockAndData` で丸太 17/162・葉 18/161 を指定の 16 ビット ID に）、ネザー（`NEID_addFeatureIn`、`HellRandomLevelSource::postProcess` `0x1008C06A4` の中の `FoliageColor::buildGrassColor` `0x1007A27F0` の呼び出しから）、色を立方体のブロックアイテム（`BlockTessellator::appendTessellatedBlock` の頂点色オフ `0x1003A2848` を中継コードに）と破片（`TerrainParticle::init` の `BlockGraphics` からの 1 バイト ID `0x100354C48` を、破片のデータの 16 ビット ID に）にも、`cloneBlock` の大きさの上限を 1MB に（`LeafBlock` は 0x24000）、`LevelRenderer::allChanged`（`0x1003F8BFC`）のフックで描画設定（`onGraphicsModeChanged`、Block vtable 89 / BlockGraphics vtable 9）を 256 以上のブロックにも | 実機確認済み（2026-11-05、鉱石・花の群れ・地表の 1 ブロック、ヒスイランの複製のデータ値、青く色を付けたタンポポの設置・生成・ドロップ、赤い丸太とピンクの葉の大きな木、ネザーの鉱石、手持ち・インベントリ・ドロップ・破片の色、葉の複製が透けること・描画の設定の切り替え。マルチプレイも 2 台で確認済み） |
| 7e | 残りの取りこぼしの点検（表の添字・`getBlockAndData` 系の呼び出し元 582 か所・Block と分かる 1 バイト読み取り・FullBlock の 1 バイトから表を引く関数）。直したもの: 描画用の明るさのキャッシュ `BlockTessallatorCache::getLightColor` が `Block::getLightEmission(BlockID)`（`0x1007D9FB4`）を 1 バイトの ID で引いていた（`0x1003A6DC8` / `0x1003A6E98` で Block を記録、`0x1003A6DD8` / `0x1003A6EA8` の呼び出しを 16 ビットの表に）。道具の耐久値: `GameMode::destroyBlock` が `ItemInstance::mineBlock` に 1 バイトで渡していた（`0x100720850` で代わりのブロック＝複製元を渡し 16 ビット ID を `tMineId` に、`DiggerItem` / `WeaponItem::mineBlock` の `0x100731854` / `0x100746E18` は 16 ビット）。トロッコに表示するブロック: 「ID が 1〜254」の判定 3 か所（`0x1006FBECC` / `0x1006FC11C` / `0x1006FC5CC`）を 1〜65535 に、ID の `LDRB` 2 か所（`0x1006FC148` / `0x1006FC650`）を `LDRH` に、描画 `renderMinecartContents` のメッシュ（`0x1003D32F0`）に 6b の描画メモ。あわせてバニラのバグ: 取得側 9 か所がトロッコにないエンティティデータ 20 / 21 を読んでいた（設定側は 16 / 17）のを 16 / 17 に。NEIDTest は普通のトロッコに test_block を表示 | 実機確認済み（2026-11-05、ツルハシ・剣・ハサミの耐久値。2026-11-06、トロッコの表示ブロックの表示・保存、チェスト付き・ホッパー付き・TNT のトロッコはそのまま） |

## 決めたこと

- **FullBlock の新しい形**: `{ uint16_t id @+0; uint8_t data @+2; uint8_t pad }`（4 バイト）。
  - ID の読み取りは `LDRB [fb]` → `LDRH [fb]`、データ値は `LDRB [fb,#1]` → `LDRB [fb,#2]` と、1 命令ずつの置き換えで済むため。
  - レジスタに詰めた形は `id | data << 8` → `id | data << 16`。
- **BlockID の受け渡し**: `getBlockID` が書く 1 バイトを 2 バイトにする。
- **チャンクの上位バイト**: `LevelChunk+87120` から 32,768 バイト。添字は下位バイト（`+0xA88`）と同じ。
- **段階 4 の進め方**: 全体の BlockID を一度に 2 バイトにするのではなく、流れごとに広げる。ブロックの取得（4a）→ 設置（4b）→ 描画・ライティング（段階 5）。256 以上の ID が関わらない限りバニラと同じ動作になるようにする。
- **中継コードの領域**: dylib 内に 8192 命令分（`neidCaveArea`、7d で 4096 から拡大）。使用量はログの `caves N/8192`（4d 完了時点で 1078、7c 完了時点で 4386。7d・7e の中継コードはこの行のあとに作る）。
- **命令の照合**: IDA が `MOV Wd, #imm` と表示する命令は、`MOVZ` のことも `ORR Wd, WZR, #imm`（ビットマスク即値）のこともある（例: `MOV W28,#1` = `0x320003FC`、`MOV W9,#2` = `0x321F03E9`）。照合では両方を受け付ける。
- **クリエイティブの表示**: ブロックアイテムはブロック側の分類（`Block+0x90`、0 = 表示しない）でタブが決まる。
- **Block のコンストラクタ** の `LDRB [X19,#8]` 2 か所（`0x1007D7F8C` / `0x1007D7F98`）は段階 2 の解析から漏れていたので 4b で追加（`mSolid[id]` / `mLightBlock[id]`）。

## 調査結果

### ID 受け渡しの書き込み先（`tools/slots.py`）

`getBlockID`（`0x10079A014`、x8 に 1 バイト）と `getBlockAndData`（`0x10079A1FC`、x8 に 2 バイト）の呼び出し元で、書き込み先のスタック領域を 4 バイトまで広げられるか。
IDA の変数名（`var_XX`）を基準にした位置で、ほかのアクセスと重なるかを調べた。

| 関数 | 広げても重ならない | 重なる（要・生存期間の確認） | スタック以外 |
|---|---|---|---|
| getBlockID | 297 | 26 | 15 |
| getBlockAndData | 126 | 21 | 5 |

重なる 47 か所の多くは、同じ領域を時間をずらして使い回している（コンパイラのスタック共有）。生存期間の解析で安全かを確かめる。

### チャンク配列の直接アクセス

`#0xA88` を使う命令は 68 か所（`ADD #0xA88` 28、`LDRB` 20、`STRB` 13 ほか）。関数単位で書き直す。
データ値のニブル配列は `+35464`。

### 主なアドレス

| アドレス | 内容 |
|---|---|
| `0x1008461D4` | `LevelChunk::LevelChunk` |
| `0x1005D4CC0` / `0x1005D4D74` | `LevelChunk` 用プールの確保 / 解放（プール `0x101247BB8`、要素サイズは +8） |
| `0x10084E528` | プールの要素サイズ（この版では `MOVZ W1,#1,LSL#16` + `MOVK W1,#0x5450`。`MOVK` 側を書き換え） |
| `0x100849944` / `0x10084A164` | `LevelChunk::serializeTerrain` / `deserializeTerrain`（通信のみで使用） |
| `0x10084AE84` | `LevelChunk::deserialize`（LevelDB から読んだキー一式。要素 32 バイト `{string tag; int begin; int end}` + 後ろに `string data`） |
| `0x1008D6160` | `DBChunkStorage::_serializeChunk`（キー = ChunkPos 8 バイト [+ 次元 ID 4 バイト] + タグ） |
| `0x100DBDB8C` / `0x100DBDBFC` | `leveldb::WriteBatch::Put` / `Delete` |
| `0x10053D040` | チャンク送信（`ServerPlayer::_sendQueuedChunk` 相当。terrain の後ろに別データが続く） |
| `+0x151C0` / `+0x151C4` | チャンクの「地形が変更された」印（セーブの対象になる） |
| `0x10079A014` | `BlockSource::getBlockID`（x8 に BlockID） |
| `0x10079A1FC` | `BlockSource::getBlockAndData`（x8 に FullBlock） |
| `0x10079B854` | `BlockSource::setBlockAndData(BlockPos const&, FullBlock const&, int flags, unique_ptr<BlockEntity>&)`（オーバーロードの集約先） |
| `0x100847490` | `LevelChunk::setBlockAndData`（呼び出し元は上の 1 か所。x8 に古い FullBlock） |
| `0x10084726C` / `0x100846BB8` / `0x1008467BC` | `LevelChunk::_removeCallbacks` / `_placeCallbacks` / ブロックエンティティ生成（BlockID はポインタ渡し） |
| `0x1007281E0` / `0x10113EAF8` | `BlockItem::BlockItem(name, short id - 256)` / BlockItem の vtable |
| `0x1007282D8` | `BlockItem::useOn`（`Item+0x6E` の 1 バイトで mayPlace・setBlockAndData・音） |
| `0x100756524` / `0x100756C70` / `0x100756D24` | `ItemInstance::init` と 2 つのコンストラクタ（`mItem` +0x10、`mBlock` +0x18） |
| `Item+0x2E` / `Item+0x6E` / `Item+0x70` | `Item::mId`（16 ビット） / ブロックアイテムのブロックID（1 バイト。+0x6F は別のフィールド） / クリエイティブの分類 |
| `0x100388338` / `0x1003829C8` | `BlockGraphics::BlockGraphics(std::string const&)`（0x3C0 バイト）/ `setTextureItem`（6 面: 上・下・北・南・西・東） |
| `0x1003845E0` / `0x100384408` | `BlockGraphics::initBlocks` / blocks.json の 1 項目から作って登録（所有リスト `0x10126A900`、`mBlocks[bg+8]`） |
| `0x10126A0F0` | `BlockGraphics::mTerrainTextureAtlas`。`BlockGraphics+0x40` は音の種類、`+0x20` は形 |
| `0x10074242C` | `Item::initClientData`（`BlockGraphics::initBlocks` の直後に呼ばれる。リソース再読み込みのたびにも） |
| `0x10079971C` / `0x10079FDA0` | `BlockSource::getBlock(BlockPos)` / `getBlock(x,y,z)`（段階 4a で置き換え） |
| `0x10084438C` / `0x100843D60` | `ChunkSource` のチャンク取得（BlockSource+0x10 のフラグで使い分け、+0x20 が ChunkSource、+0x58 が直前のチャンク） |
| `0x1012D1843` | 範囲外・未読み込みのときに返すブロックID |
| `0x10079AD80` | `BlockSource::getMaterial` 系（161 か所から呼ばれる） |
| `0x101146080` | `Block` の vtable（113 スロット）。サブクラスの vtable は 138 個 |

## 解析スクリプト（`tools/`）

入力ファイルは IDA の出力（`minecraftpe.asm` / `.c` / `.lst`）から作る。

- `insns.txt`: `.asm` から命令行だけを抜き出したもの
  `grep -E "^0000000100[0-9A-F]{6} +[A-Z]" minecraftpe.asm | grep -v -E "^0000000100[0-9A-F]{6} +DC[BDQW]? "`
- `labels.txt`: 分岐先ラベルのアドレス、`funcs.txt`: 関数の開始アドレス（`.c` の `//----- (...)`）
- `dcq.txt`: `__const` / `__data` の `DCQ` ポインタ
- `blockstatics.txt`: `Block::initBlocks` で代入される `Block::mXxx`（195 個）

| スクリプト | 内容 |
|---|---|
| `vt.py` | `Block` のサブクラスの vtable と、その関数（`this` が Block）を求める |
| `rd.py` | 制御フローを使った到達定義解析。`LDRB [Xn,#8]` の `Xn` が全経路で Block かを判定（段階 2 の 3,082 か所） |
| `slots.py` | ID 受け渡しの書き込み先を広げられるかを調べる |
| `cls.py` / `idx.py` | アイテムID（`Item::mId`）の読み取り元の分類（アイテム拡張で使用） |
| `audit.py` | 7e の点検: まだ書き換えていない `LDRB [Xn,#8]` のうち、`Xn` の到達定義のどれかが Block（`this`・`getBlock` の戻り値・`mBlocks[i]`・静的変数）か BlockGraphics の表から来るものを列挙（`rd.py` を使う。`python audit.py Tweak.xm`） |
| `fbtab.py` | 7e の点検: FullBlock の 1 バイトの ID（`LDRB Wn, [Xm]`）でブロックIDの表を引く場所を列挙 |
