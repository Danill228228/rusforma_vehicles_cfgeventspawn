// RF_Humvee_Hatch — люк на крыше RF_Humvee: действия «Открыть люк» / «Закрыть люк»
// из салона и снаружи (с крыши), сохранение положения люка.
// Деталь люка с анимацией (model.cfg, источник HatchRoof) и его состояние — в основном аддоне RF_Humvee.

class CfgPatches
{
	class RF_Humvee_Hatch
	{
		units[] = {};
		weapons[] = {};
		requiredVersion = 0.1;
		requiredAddons[] = {"RF_Humvee"};
	};
};

class CfgMods
{
	class RF_Humvee_Hatch
	{
		dir = "RF_Humvee_Hatch";
		name = "RF Humvee Hatch";
		author = "RF";
		type = "mod";
		dependencies[] = {"World"};
		class defs
		{
			class worldScriptModule
			{
				value = "";
				files[] = {"RF_Humvee_Hatch/scripts/4_World"};
			};
		};
	};
};
