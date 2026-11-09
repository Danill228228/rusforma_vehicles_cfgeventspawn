// HatchP0 — одноразовый тестовый мод (прототип P0). НЕ для боевых серверов.
// Проверяет, можно ли закрепить игрока на крыше ванильного Offroad_02
// и стрелять на ходу. Подробности: prototype/README.md

class CfgPatches
{
	class HatchP0
	{
		units[] = {};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Vehicles_Wheeled"};
	};
};

class CfgMods
{
	class HatchP0
	{
		dir = "HatchP0";
		picture = "";
		action = "";
		hideName = 1;
		hidePicture = 1;
		name = "HatchP0 (test)";
		credits = "";
		author = "";
		authorID = "0";
		version = "0.1";
		extra = 0;
		type = "mod";
		dependencies[] = {"World", "Mission"};

		class defs
		{
			class worldScriptModule
			{
				value = "";
				files[] = {"HatchP0/scripts/4_World"};
			};
			class missionScriptModule
			{
				value = "";
				files[] = {"HatchP0/scripts/5_Mission"};
			};
		};
	};
};

class CfgVehicles
{
	class CarScript;
	class Offroad_02: CarScript
	{
		// Тест T3: начнёт ли движок сам удерживать игрока, стоящего на машине,
		// если задать «лодочный» параметр? В ванили он есть только у лодок (Boat_01_ColorBase = 5).
		// 30 м/с ≈ 108 км/ч, поэтому на тестовых скоростях до 60 км/ч не мешает.
		animPhysDetachSpeed = 30;
	};
};
