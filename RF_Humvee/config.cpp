// RF_Humvee — HMMWV-подобный бронированный внедорожник с открываемым люком на крыше.
// Наследуется от ванильного OffroadHatchback (Ada 4x4), чтобы взять готовую физику, звук и двигатель.
// P3D-модели собираются из RF_Humvee/model/humvee.obj (см. README.md).

class CfgPatches
{
	class RF_Humvee
	{
		units[] = {"RF_Humvee", "RF_Humvee_Desert", "RF_HumveeWheel"};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"DZ_Data", "DZ_Scripts", "DZ_Vehicles_Wheeled", "DZ_Vehicles_Parts"};
	};
};

class CfgMods
{
	class RF_Humvee
	{
		dir = "RF_Humvee";
		name = "RF Humvee";
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

class CfgSlots
{
	class Slot_RF_HumveeWheel_1_1 { name = "RF_HumveeWheel_1_1"; displayName = "Колесо (ЛП)"; ghostIcon = "set:dayz_inventory image:wheel"; };
	class Slot_RF_HumveeWheel_1_2 { name = "RF_HumveeWheel_1_2"; displayName = "Колесо (ЛЗ)"; ghostIcon = "set:dayz_inventory image:wheel"; };
	class Slot_RF_HumveeWheel_2_1 { name = "RF_HumveeWheel_2_1"; displayName = "Колесо (ПП)"; ghostIcon = "set:dayz_inventory image:wheel"; };
	class Slot_RF_HumveeWheel_2_2 { name = "RF_HumveeWheel_2_2"; displayName = "Колесо (ПЗ)"; ghostIcon = "set:dayz_inventory image:wheel"; };
};

class CfgVehicles
{
	class CarWheel;
	class CarScript;
	class OffroadHatchback: CarScript
	{
		class AnimationSources;
		class SimulationModule;
	};

	// ------------------------------------------------------------------ колесо
	class RF_HumveeWheel: CarWheel
	{
		scope = 2;
		displayName = "Колесо Humvee";
		descriptionShort = "Внедорожное колесо 37x12.5 R16.5 с бедлоком.";
		model = "\RF_Humvee\data\rf_humvee_wheel.p3d";
		weight = 42000;
		itemSize[] = {9, 9};
		inventorySlot[] = {"RF_HumveeWheel_1_1", "RF_HumveeWheel_1_2", "RF_HumveeWheel_2_1", "RF_HumveeWheel_2_2"};
		rotationFlags = 4;
		radiusByDamage[] = {0, 0.475, 0.3, 0.44, 0.9998, 0.36, 0.9999, 0.30};
		radius = 0.475;
		width = 0.32;
		tyreRollResistance = 0.018;
		tyreTread = 0.8;
	};

	// ------------------------------------------------------------------ машина
	class RF_Humvee: OffroadHatchback
	{
		scope = 2;
		displayName = "Humvee M1025";
		descriptionShort = "Армейский внедорожник с жёсткой бронированной крышей и люком стрелка.";
		model = "\RF_Humvee\data\rf_humvee.p3d";

		hiddenSelections[] = {"camo"};
		hiddenSelectionsTextures[] = {"\RF_Humvee\data\rf_humvee_olive_co.paa"};

		attachments[] =
		{
			"CarBattery",
			"Reflector_1_1",
			"Reflector_2_1",
			"CarRadiator",
			"SparkPlug",
			"RF_HumveeWheel_1_1",
			"RF_HumveeWheel_1_2",
			"RF_HumveeWheel_2_1",
			"RF_HumveeWheel_2_2"
		};

		class AnimationSources: AnimationSources
		{
			// Люк на крыше: 0 = закрыт, 1 = открыт. Ставится из скрипта через SetAnimationPhase("HatchRoof", ...)
			class HatchRoof
			{
				source = "user";
				animPeriod = 1.2;
				initPhase = 0;
			};
		};

		class SimulationModule: SimulationModule
		{
			class Axles: Axles
			{
				class Front: Front
				{
					class Wheels: Wheels
					{
						class Left: Left   { inventorySlot = "RF_HumveeWheel_1_1"; };
						class Right: Right { inventorySlot = "RF_HumveeWheel_2_1"; };
					};
				};
				class Rear: Rear
				{
					class Wheels: Wheels
					{
						class Left: Left   { inventorySlot = "RF_HumveeWheel_1_2"; };
						class Right: Right { inventorySlot = "RF_HumveeWheel_2_2"; };
					};
				};
			};
		};
	};

	class RF_Humvee_Desert: RF_Humvee
	{
		displayName = "Humvee M1025 (пустынный)";
		hiddenSelectionsTextures[] = {"\RF_Humvee\data\rf_humvee_desert_co.paa"};
	};
};
