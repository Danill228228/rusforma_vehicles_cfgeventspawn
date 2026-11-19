// RF_Humvee — ванильный HMMWV M1025 (Offroad_02) с открываемым люком стрелка на крыше.
// Модель, двери, капот, багажник, колёса, физика, звук и повреждения — из игры (наследование, файлы не копируются).
// Мод добавляет деталь люка RF_HumveeHatch: клиент прикрепляет её к машине поверх ванильной крышки кольца турели.
// Действия «Открыть/Закрыть люк» — в отдельном аддоне RF_Humvee_Hatch.

class CfgPatches
{
	class RF_Humvee
	{
		units[] = {"RF_Humvee", "RF_Humvee_Desert"};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Vehicles_Wheeled"};
	};
};

class CfgMods
{
	class RF_Humvee
	{
		dir = "RF_Humvee";
		name = "RF Humvee";
		author = "RF";
		type = "mod";
		dependencies[] = {"World"};
		class defs
		{
			class worldScriptModule
			{
				value = "";
				files[] = {"RF_Humvee/scripts/4_World"};
			};
		};
	};
};

class CfgVehicles
{
	class Offroad_02;
	class Offroad_02_Beige;
	class HouseNoDestruct;

	// Окраска, материалы, детали и повреждения — ванильные (Offroad_02 и Offroad_02_Beige).
	class RF_Humvee: Offroad_02
	{
		scope = 2;
		displayName = "Humvee M1114";
		descriptionShort = "Армейский HMMWV с открываемым люком стрелка на крыше.";
	};

	class RF_Humvee_Desert: Offroad_02_Beige
	{
		scope = 2;
		displayName = "Humvee M1114 (пустынный)";
		descriptionShort = "Армейский HMMWV с открываемым люком стрелка на крыше.";
	};

	// Деталь люка: только картинка (без геометрии и коллизии), создаётся у клиента локально (ECE_LOCAL).
	class RF_HumveeHatch: HouseNoDestruct
	{
		scope = 1;
		model = "\RF_Humvee\data\rf_humvee_hatch.p3d";
		hiddenSelections[] = {"camo"};
		hiddenSelectionsTextures[] = {"dz\vehicles\wheeled\offroad_02\data\offroad_02_roof_co.paa"};
		hiddenSelectionsMaterials[] = {"dz\vehicles\wheeled\offroad_02\data\offroad_02_roof.rvmat"};
		class AnimationSources
		{
			class HatchRoof
			{
				source = "user";
				animPeriod = 1.2;
				initPhase = 0;
			};
		};
	};

	class RF_HumveeHatch_Desert: RF_HumveeHatch
	{
		hiddenSelectionsTextures[] = {"dz\vehicles\wheeled\offroad_02\data\beige\offroad_02_roof_co.paa"};
		hiddenSelectionsMaterials[] = {"dz\vehicles\wheeled\offroad_02\data\beige\offroad_02_roof.rvmat"};
	};
};
