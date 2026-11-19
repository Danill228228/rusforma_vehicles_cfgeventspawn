// RF_Humvee — свой HMMWV M1025 с открываемым люком стрелка. Модель своя (RF_Humvee/source/m1025.py, по образцу
// ванильного M1025), а двигатель, коробка, подвеска, звуки, места экипажа и колёса — от ванильного Offroad_02
// (наследование, файлы игры не копируются). Окраска — своя текстура с износом (RF_Humvee_Mod/tools/texture_atlas.py).
// Действия «Открыть/Закрыть люк» — в отдельном аддоне RF_Humvee_Hatch.

class CfgPatches
{
	class RF_Humvee
	{
		units[] = {"RF_Humvee", "RF_Humvee_Desert"};
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
	class RF_Humvee: Offroad_02
	{
		scope = 2;
		displayName = "Humvee M1114";
		descriptionShort = "Армейский HMMWV с открываемым люком стрелка на крыше.";
		model = "\RF_Humvee\data\rf_humvee.p3d";

		// Двери, капот и багажник — части модели (не аттачменты). Колёса — ванильные колёса M1025 в своих слотах.
		doors[] = {};
		attachments[] = {"CarBattery", "Reflector_1_1", "Reflector_2_1", "GlowPlug",
			"Offroad_02_Wheel_1_1", "Offroad_02_Wheel_1_2", "Offroad_02_Wheel_2_1", "Offroad_02_Wheel_2_2"};

		// CarScript меняет материалы фар по номерам 0…8, поэтому, как у ванили, сначала фары, затем окраска camo:
		// своя текстура-атлас всей модели (камуфляж, пыль, грязь, потёртости), рельеф и блики — в rf_humvee_body.rvmat
		hiddenSelections[] = {"light_1_1", "light_2_1", "light_brake_1_2", "light_brake_2_2", "light_reverse_1_2",
			"light_reverse_2_2", "light_1_2", "light_2_2", "light_dashboard", "camo"};
		hiddenSelectionsTextures[] = {"", "", "", "", "", "", "", "", "", "\RF_Humvee\data\rf_humvee_woodland_co.paa"};
		hiddenSelectionsMaterials[] = {"", "", "", "", "", "", "", "", "", "\RF_Humvee\data\rf_humvee_body.rvmat"};

		class GUIInventoryAttachmentsProps
		{
			class Engine
			{
				name = "$STR_attachment_Engine0";
				description = "";
				icon = "cat_vehicle_engine";
				attachmentSlots[] = {"CarBattery", "GlowPlug"};
			};
			class Body
			{
				name = "$STR_attachment_Body0";
				description = "";
				icon = "cat_vehicle_body";
				attachmentSlots[] = {"Reflector_1_1", "Reflector_2_1"};
			};
			class Chassis
			{
				name = "$STR_attachment_Chassis0";
				description = "";
				icon = "cat_vehicle_chassis";
				attachmentSlots[] = {"Offroad_02_Wheel_1_1", "Offroad_02_Wheel_1_2", "Offroad_02_Wheel_2_1", "Offroad_02_Wheel_2_2"};
			};
		};

		// Источники анимаций целиком (на вложенные классы ванили без полной цепочки классов не сослаться):
		// двери, капот, багажник, люк — «user», амортизаторы — покой 0.5, как у ванильного M1025
		class AnimationSources
		{
			class DoorsDriver
			{
				source = "user";
				animPeriod = 0.5;
				initPhase = 0;
			};
			class DoorsCoDriver: DoorsDriver {};
			class DoorsCargo1: DoorsDriver {};
			class DoorsCargo2: DoorsDriver {};
			class DoorsHood
			{
				source = "user";
				animPeriod = 1.0;
				initPhase = 0;
			};
			class DoorsTrunk: DoorsHood {};
			class HatchRoof
			{
				source = "user";
				animPeriod = 1.2;
				initPhase = 0;
			};
			class damper_1_1
			{
				source = "user";
				animPeriod = 1;
				initPhase = 0.5;
			};
			class damper_2_1: damper_1_1 {};
			class damper_1_2: damper_1_1 {};
			class damper_2_2: damper_1_1 {};
		};

		// Свои зоны повреждений по компонентам и точкам своей модели (у ванили они названы под её модель)
		class DamageSystem
		{
			class GlobalHealth
			{
				class Health
				{
					hitpoints = 4000;
					healthLevels[] = {{1.0, {}}, {0.7, {}}, {0.5, {}}, {0.3, {}}, {0.0, {}}};
				};
			};
			class DamageZones
			{
				class Chassis
				{
					class Health
					{
						hitpoints = 4000;
						transferToGlobalCoef = 0;
						healthLevels[] = {{1.0, {}}, {0.7, {}}, {0.5, {}}, {0.3, {}}, {0.0, {}}};
					};
					componentNames[] = {"dmgZone_chassis"};
					memoryPoints[] = {"dmgZone_chassis"};
					fatalInjuryCoef = -1;
					inventorySlots[] = {};
				};
				class Engine
				{
					class Health
					{
						hitpoints = 1200;
						transferToGlobalCoef = 1;
						healthLevels[] = {{1.0, {}}, {0.7, {}}, {0.5, {}}, {0.3, {}}, {0.0, {}}};
					};
					componentNames[] = {"dmgZone_engine"};
					memoryPoints[] = {"dmgZone_engine"};
					fatalInjuryCoef = 0.001;
					inventorySlots[] = {"CarBattery", "GlowPlug"};
					inventorySlotsCoefs[] = {0.3, 0.3};
				};
				// CarScript.EEItemAttached ищет зону с именем слота фары: без неё "Could not find zone Reflector_1_1"
				class Reflector_1_1
				{
					class Health
					{
						hitpoints = 10;
						transferToGlobalCoef = 0;
						healthLevels[] = {{1.0, {}}, {0.7, {}}, {0.5, {}}, {0.3, {}}, {0.0, {}}};
					};
					componentNames[] = {};
					memoryPoints[] = {"light_1_1"};
					fatalInjuryCoef = -1;
					inventorySlots[] = {"Reflector_1_1"};
				};
				class Reflector_2_1: Reflector_1_1
				{
					memoryPoints[] = {"light_2_1"};
					inventorySlots[] = {"Reflector_2_1"};
				};
				class FuelTank
				{
					class Health
					{
						hitpoints = 700;
						transferToGlobalCoef = 0;
						healthLevels[] = {{1.0, {}}, {0.7, {}}, {0.5, {}}, {0.3, {}}, {0.0, {}}};
					};
					componentNames[] = {"dmgZone_fuelTank"};
					memoryPoints[] = {"dmgZone_fuelTank"};
					fatalInjuryCoef = -1;
					inventorySlots[] = {};
				};
			};
		};
	};

	class RF_Humvee_Desert: RF_Humvee
	{
		displayName = "Humvee M1114 (пустынный)";
		hiddenSelectionsTextures[] = {"", "", "", "", "", "", "", "", "", "\RF_Humvee\data\rf_humvee_desert_co.paa"};
	};
};
