// RF_Humvee — бронированный HMMWV-подобный внедорожник.
// Этот аддон отвечает только за то, чтобы машина была в игре: модель, колёса, места, физика.
// Люк (действия «Открыть/Закрыть люк») — в отдельном аддоне RF_Humvee_Hatch.

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

class CfgSlots
{
	class Slot_RF_HumveeWheel_1_1 { name = "RF_HumveeWheel_1_1"; displayName = "Колесо (левое переднее)"; selection = "wheel_1_1"; ghostIcon = "set:dayz_inventory image:wheel"; };
	class Slot_RF_HumveeWheel_1_2 { name = "RF_HumveeWheel_1_2"; displayName = "Колесо (левое заднее)";  selection = "wheel_1_2"; ghostIcon = "set:dayz_inventory image:wheel"; };
	class Slot_RF_HumveeWheel_2_1 { name = "RF_HumveeWheel_2_1"; displayName = "Колесо (правое переднее)"; selection = "wheel_2_1"; ghostIcon = "set:dayz_inventory image:wheel"; };
	class Slot_RF_HumveeWheel_2_2 { name = "RF_HumveeWheel_2_2"; displayName = "Колесо (правое заднее)";  selection = "wheel_2_2"; ghostIcon = "set:dayz_inventory image:wheel"; };
};

class CfgVehicles
{
	class CarWheel;
	class CarScript;
	class OffroadHatchback: CarScript
	{
		class SimulationModule;
	};

	// ------------------------------------------------------------------ колесо
	class RF_HumveeWheel: CarWheel
	{
		scope = 2;
		displayName = "Колесо Humvee";
		descriptionShort = "Внедорожное колесо 37x12.5 R16.5.";
		model = "\RF_Humvee\data\rf_humvee_wheel.p3d";
		weight = 40000;
		itemSize[] = {8, 8};
		inventorySlot[] = {"RF_HumveeWheel_1_1", "RF_HumveeWheel_1_2", "RF_HumveeWheel_2_1", "RF_HumveeWheel_2_2"};
		rotationFlags = 8;
		physLayer = "item_large";
		radiusByDamage[] = {0, 0.482, 0.3, 0.44, 0.9998, 0.36, 0.9999, 0.30};
		radius = 0.482;
		width = 0.36;
		friction = 0.95;
		tyreRollResistance = 0.018;
		tyreTread = 0.8;
		tyreOffroadResistance = 0.7;
		tyreGrip = 1.0;
	};

	// ------------------------------------------------------------------ машина
	// Конфиг наследует звук, двигатель и коробку от ванильного Ada 4x4 (OffroadHatchback),
	// а места, колёса, повреждения и инвентарь задаёт свои.
	class RF_Humvee: OffroadHatchback
	{
		scope = 2;
		displayName = "Humvee M1114";
		descriptionShort = "Армейский бронированный внедорожник с люком стрелка на крыше.";
		model = "\RF_Humvee\data\rf_humvee.p3d";
		modelZeroPointDistanceFromGround = 0;
		fuelCapacity = 95;
		fuelConsumption = 14;

		hiddenSelections[] = {"camo"};
		hiddenSelectionsTextures[] = {"\RF_Humvee\data\rf_humvee_woodland_co.paa"};
		hiddenSelectionsMaterials[] = {""};

		doors[] = {};
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

		class GUIInventoryAttachmentsProps
		{
			class Engine
			{
				name = "$STR_attachment_Engine0";
				description = "";
				icon = "cat_vehicle_engine";
				attachmentSlots[] = {"CarBattery", "CarRadiator", "SparkPlug"};
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
				attachmentSlots[] = {"RF_HumveeWheel_1_1", "RF_HumveeWheel_1_2", "RF_HumveeWheel_2_1", "RF_HumveeWheel_2_2"};
			};
		};

		class Cargo
		{
			itemsCargoSize[] = {10, 60};
			allowOwnedCargoManipulation = 1;
			openable = 0;
		};

		class AnimationSources
		{
			class HatchRoof
			{
				source = "user";
				animPeriod = 1.2;
				initPhase = 0;
			};
		};

		class Crew
		{
			class Driver
			{
				actionSel = "seat_driver";
				proxyPos = "crewDriver";
				getInPos = "pos_driver";
				getInDir = "pos_driver_dir";
				isDriver = 1;
			};
			class CoDriver
			{
				actionSel = "seat_codriver";
				proxyPos = "crewCoDriver";
				getInPos = "pos_codriver";
				getInDir = "pos_codriver_dir";
			};
			class Cargo1
			{
				actionSel = "seat_cargo1";
				proxyPos = "crewCargo1";
				getInPos = "pos_cargo1";
				getInDir = "pos_cargo1_dir";
			};
			class Cargo2
			{
				actionSel = "seat_cargo2";
				proxyPos = "crewCargo2";
				getInPos = "pos_cargo2";
				getInDir = "pos_cargo2_dir";
			};
		};

		class SimulationModule: SimulationModule
		{
			drive = "DRIVE_AWD";
			class Steering
			{
				maxSteeringAngle = 32;
				increaseSpeed[] = {0, 45, 60, 23, 100, 12};
				decreaseSpeed[] = {0, 80, 60, 40, 90, 20};
				centeringSpeed[] = {0, 0, 15, 25, 60, 40, 100, 60};
			};
			class Engine
			{
				torqueCurve[] = {600, 0, 900, 220, 1600, 360, 2600, 400, 3600, 320, 4200, 0};
				inertia = 0.25;
				frictionTorque = 140;
				rollingFriction = 1.0;
				viscousFriction = 1.0;
				rpmIdle = 800;
				rpmMin = 900;
				rpmClutch = 1300;
				rpmRedline = 3600;
			};
			class Axles: Axles
			{
				class Front: Front
				{
					maxBrakeTorque = 5000;
					maxHandbrakeTorque = 6000;
					wheelHubMass = 10;
					wheelHubRadius = 0.2;
					class Suspension
					{
						stiffness = 52000;
						compression = 6500;
						damping = 11000;
						travelMaxUp = 0.16;
						travelMaxDown = 0.16;
					};
					class Wheels: Wheels
					{
						class Left: Left
						{
							animTurn = "turnfrontleft";
							animRotation = "wheelfrontleft";
							animDamper = "damper_1_1";
							wheelHub = "wheel_1_1_damper_land";
							inventorySlot = "RF_HumveeWheel_1_1";
						};
						class Right: Right
						{
							animTurn = "turnfrontright";
							animRotation = "wheelfrontright";
							animDamper = "damper_2_1";
							wheelHub = "wheel_2_1_damper_land";
							inventorySlot = "RF_HumveeWheel_2_1";
						};
					};
				};
				class Rear: Rear
				{
					maxBrakeTorque = 4600;
					maxHandbrakeTorque = 6000;
					wheelHubMass = 10;
					wheelHubRadius = 0.2;
					class Suspension
					{
						stiffness = 56000;
						compression = 6500;
						damping = 11500;
						travelMaxUp = 0.16;
						travelMaxDown = 0.16;
					};
					class Wheels: Wheels
					{
						class Left: Left
						{
							animTurn = "turnbackleft";
							animRotation = "wheelbackleft";
							animDamper = "damper_1_2";
							wheelHub = "wheel_1_2_damper_land";
							inventorySlot = "RF_HumveeWheel_1_2";
						};
						class Right: Right
						{
							animTurn = "turnbackright";
							animRotation = "wheelbackright";
							animDamper = "damper_2_2";
							wheelHub = "wheel_2_2_damper_land";
							inventorySlot = "RF_HumveeWheel_2_2";
						};
					};
				};
			};
		};

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
					inventorySlots[] = {"CarBattery", "SparkPlug", "CarRadiator"};
					inventorySlotsCoefs[] = {0.3, 0.3, 0.3};
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
		hiddenSelectionsTextures[] = {"\RF_Humvee\data\rf_humvee_desert_co.paa"};
	};
};
