// =====================================================================================
// Offroad_02 (M1025): внутриигровая диагностика верхнего люка.
//
// Где запускать: DayZDiag_x64.exe, офлайн-миссия или локальный диаг-сервер,
// Script Console -> вкладка «Enforce Script» -> вставить весь текст -> Run.
// Вывод пишется в скрипт-лог (Documents\DayZ\Logs\script_*.log или папка профиля
// сервера); фильтруйте по метке [HATCHDIAG].
//
// Что делает (только чтение, машину не изменяет):
//   1. Находит Offroad_02 в радиусе 20 м от игрока или создаёт её в 6 м перед ним.
//   2. Выводит путь к модели и ВСЕ named selection модели.
//   3. Для каждого источника анимации из списка выводит, сколько костей он двигает
//      (GetBonePivotsForAnimationSource). Источники дверей — контрольная группа:
//      у них должно быть > 0. Если кандидат на люк даёт 0 во всех LOD, анимации
//      с таким именем в модели нет.
//   4. Проверяет memory points мест и крыши и выводит трансформы мест
//      (нужны, чтобы разместить игрока в люке).
//
// Имена, найденные tools/hmmwv_hatch/p3d_names.py, добавьте в hd_sources.
// =====================================================================================

PlayerBase hd_player = PlayerBase.Cast(GetGame().GetPlayer());
Offroad_02 hd_car;

array<Object> hd_objs = new array<Object>;
GetGame().GetObjectsAtPosition(hd_player.GetPosition(), 20, hd_objs, null);
foreach (Object hd_o : hd_objs)
{
	if (Class.CastTo(hd_car, hd_o))
		break;
}

if (!hd_car)
{
	vector hd_spawnPos = hd_player.GetPosition() + (hd_player.GetDirection() * 6);
	hd_car = Offroad_02.Cast(GetGame().CreateObjectEx("Offroad_02", hd_spawnPos, ECE_PLACE_ON_SURFACE));
	if (hd_car)
		hd_car.OnDebugSpawn();
}

if (!hd_car)
{
	Print("[HATCHDIAG] ОШИБКА: не удалось найти или создать Offroad_02");
}
else
{
	Print("[HATCHDIAG] тип=" + hd_car.GetType() + " модель=" + hd_car.ConfigGetString("model"));

	// --- 1. Named selections ---
	TStringArray hd_selections = new TStringArray;
	hd_car.GetSelectionList(hd_selections);
	Print("[HATCHDIAG] всего selection=" + hd_selections.Count());
	foreach (string hd_sel : hd_selections)
	{
		Print("[HATCHDIAG] selection: " + hd_sel);
	}

	// --- 2. Источники анимаций -> кости ---
	TStringArray hd_sources = {
		// контрольная группа (известны из config.cpp, должно быть > 0)
		"DoorsDriver", "DoorsCoDriver", "DoorsCargo1", "DoorsCargo2", "DoorsHood", "DoorsTrunk",
		// кандидаты на люк (добавьте имена из p3d_names.py)
		"Hatch", "DoorsHatch", "Hatch_1", "HatchGunner", "Turret", "Poklop", "Roof", "DoorsRoof"
	};

	array<int> hd_levels = new array<int>;
	hd_levels.Insert(hd_car.GetViewGeometryLevel());
	hd_levels.Insert(hd_car.GetGeometryLevel());
	hd_levels.Insert(hd_car.GetFireGeometryLevel());
	hd_levels.Insert(hd_car.GetMemoryLevel());

	foreach (string hd_src : hd_sources)
	{
		string hd_line = hd_src + " фаза=" + hd_car.GetAnimationPhase(hd_src).ToString();
		foreach (int hd_lvl : hd_levels)
		{
			TIntArray hd_pivots = new TIntArray;
			hd_car.GetBonePivotsForAnimationSource(hd_lvl, hd_src, hd_pivots);
			hd_line = hd_line + " | lod" + hd_lvl.ToString() + "=" + hd_pivots.Count().ToString();
		}
		Print("[HATCHDIAG] источник " + hd_line);
	}

	// --- 3. Memory points ---
	TStringArray hd_memPoints = {
		"pos_driver", "pos_coDriver", "pos_cargo1", "pos_cargo2",
		"dmgZone_roof", "hatch", "pos_hatch", "pos_gunner", "turret", "gunnerview"
	};
	foreach (string hd_mp : hd_memPoints)
	{
		bool hd_exists = hd_car.MemoryPointExists(hd_mp);
		string hd_mpLine = hd_mp + " есть=" + hd_exists.ToString();
		if (hd_exists)
			hd_mpLine = hd_mpLine + " поз(MS)=" + hd_car.GetMemoryPointPos(hd_mp).ToString();
		Print("[HATCHDIAG] memorypoint " + hd_mpLine);
	}

	// --- 4. Трансформы мест и высота крыши ---
	vector hd_tm[4];
	for (int hd_i = 0; hd_i < hd_car.CrewSize(); hd_i++)
	{
		hd_car.CrewTransform(hd_i, hd_tm);
		Print("[HATCHDIAG] место " + hd_i.ToString() + " анимСиденья=" + hd_car.GetSeatAnimationType(hd_i).ToString() + " поз(MS)=" + hd_tm[3].ToString());
	}

	vector hd_box[2];
	if (hd_car.GetCollisionBox(hd_box))
		Print("[HATCHDIAG] коллизия мин=" + hd_box[0].ToString() + " макс=" + hd_box[1].ToString());
}
