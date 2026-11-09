// =====================================================================================
// Offroad_02 (M1025): in-game diagnostic for the roof hatch.
//
// Where to run it: DayZDiag_x64.exe, offline mission or a local diag server,
// Script Console -> "Enforce Script" tab -> paste everything -> Run.
// The output goes to the script log (Documents\DayZ\Logs\script_*.log or the
// server profile folder); filter on the [HATCHDIAG] marker.
//
// What it does (read-only, changes nothing on the car):
//   1. Finds an Offroad_02 within 20 m of the player, or spawns one 6 m in front.
//   2. Prints the model path and ALL named selections of the model.
//   3. For each animation source in the list, prints how many bones it drives
//      (GetBonePivotsForAnimationSource). The door sources are a control group:
//      they must return > 0. If a hatch candidate returns 0 in every LOD, the model
//      has no animation under that name.
//   4. Checks the memory points of the seats and the roof, and prints the seat
//      transforms (needed to place the player in the hatch).
//
// Add the names found by tools/hmmwv_hatch/p3d_names.py to hd_sources.
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
	Print("[HATCHDIAG] ERROR: failed to find or create Offroad_02");
}
else
{
	Print("[HATCHDIAG] type=" + hd_car.GetType() + " model=" + hd_car.ConfigGetString("model"));

	// --- 1. Named selections ---
	TStringArray hd_selections = new TStringArray;
	hd_car.GetSelectionList(hd_selections);
	Print("[HATCHDIAG] selections count=" + hd_selections.Count());
	foreach (string hd_sel : hd_selections)
	{
		Print("[HATCHDIAG] selection: " + hd_sel);
	}

	// --- 2. Animation sources -> bones ---
	TStringArray hd_sources = {
		// control group (known from config.cpp, must be > 0)
		"DoorsDriver", "DoorsCoDriver", "DoorsCargo1", "DoorsCargo2", "DoorsHood", "DoorsTrunk",
		// hatch candidates (add names from p3d_names.py)
		"Hatch", "DoorsHatch", "Hatch_1", "HatchGunner", "Turret", "Poklop", "Roof", "DoorsRoof"
	};

	array<int> hd_levels = new array<int>;
	hd_levels.Insert(hd_car.GetViewGeometryLevel());
	hd_levels.Insert(hd_car.GetGeometryLevel());
	hd_levels.Insert(hd_car.GetFireGeometryLevel());
	hd_levels.Insert(hd_car.GetMemoryLevel());

	foreach (string hd_src : hd_sources)
	{
		string hd_line = hd_src + " phase=" + hd_car.GetAnimationPhase(hd_src).ToString();
		foreach (int hd_lvl : hd_levels)
		{
			TIntArray hd_pivots = new TIntArray;
			hd_car.GetBonePivotsForAnimationSource(hd_lvl, hd_src, hd_pivots);
			hd_line = hd_line + " | lod" + hd_lvl.ToString() + "=" + hd_pivots.Count().ToString();
		}
		Print("[HATCHDIAG] animsource " + hd_line);
	}

	// --- 3. Memory points ---
	TStringArray hd_memPoints = {
		"pos_driver", "pos_coDriver", "pos_cargo1", "pos_cargo2",
		"dmgZone_roof", "hatch", "pos_hatch", "pos_gunner", "turret", "gunnerview"
	};
	foreach (string hd_mp : hd_memPoints)
	{
		bool hd_exists = hd_car.MemoryPointExists(hd_mp);
		string hd_mpLine = hd_mp + " exists=" + hd_exists.ToString();
		if (hd_exists)
			hd_mpLine = hd_mpLine + " pos(MS)=" + hd_car.GetMemoryPointPos(hd_mp).ToString();
		Print("[HATCHDIAG] memorypoint " + hd_mpLine);
	}

	// --- 4. Seat transforms and roof height ---
	vector hd_tm[4];
	for (int hd_i = 0; hd_i < hd_car.CrewSize(); hd_i++)
	{
		hd_car.CrewTransform(hd_i, hd_tm);
		Print("[HATCHDIAG] crew " + hd_i.ToString() + " seatAnim=" + hd_car.GetSeatAnimationType(hd_i).ToString() + " pos(MS)=" + hd_tm[3].ToString());
	}

	vector hd_box[2];
	if (hd_car.GetCollisionBox(hd_box))
		Print("[HATCHDIAG] collisionBox min=" + hd_box[0].ToString() + " max=" + hd_box[1].ToString());
}
