// Свой HMMWV M1025 (модель RF_Humvee, по образцу ванильного M1025). Скрипт наследует ванильный Offroad_02:
// оттуда посадка и пересадка, анимации экипажа HMMWV, двигатель, звуки, доступ к двигателю при открытом капоте
// и к грузу при открытом багажнике. Двери, капот и багажник у нас — анимированные части модели, а не детали-
// аттачменты, поэтому их состояние берётся из фазы анимации по тем же ванильным именам слотов.
// Люк — в аддоне RF_Humvee_Hatch (modded class RF_Humvee).

class RF_Humvee extends Offroad_02
{
	override int GetCarDoorsState(string slotType)
	{
		switch (slotType)
		{
			case "Offroad_02_Door_1_1":
				return TranslateAnimationPhaseToCarDoorState("DoorsDriver");
			case "Offroad_02_Door_2_1":
				return TranslateAnimationPhaseToCarDoorState("DoorsCoDriver");
			case "Offroad_02_Door_1_2":
				return TranslateAnimationPhaseToCarDoorState("DoorsCargo1");
			case "Offroad_02_Door_2_2":
				return TranslateAnimationPhaseToCarDoorState("DoorsCargo2");
			case "Offroad_02_Hood":
				return TranslateAnimationPhaseToCarDoorState("DoorsHood");
			case "Offroad_02_Trunk":
				return TranslateAnimationPhaseToCarDoorState("DoorsTrunk");
		}

		return CarDoorState.DOORS_MISSING;
	}

	// Цели в View Geometry: дверь (doors_*) и неподвижная зона места в проёме (seat_*) — обе про свою дверь,
	// капот и крышка багажника
	override string GetAnimSourceFromSelection(string selection)
	{
		switch (selection)
		{
			case "seat_driver":
			case "doors_driver":
				return "DoorsDriver";
			case "seat_codriver":
			case "doors_codriver":
				return "DoorsCoDriver";
			case "seat_cargo1":
			case "doors_cargo1":
				return "DoorsCargo1";
			case "seat_cargo2":
			case "doors_cargo2":
				return "DoorsCargo2";
			case "doors_hood":
				return "DoorsHood";
			case "doors_trunk":
				return "DoorsTrunk";
		}

		return "";
	}

	// где стоять, чтобы сесть: точки pos_* у задней кромки проёма (открытая дверь уходит вперёд)
	override string GetDoorConditionPointFromSelection(string selection)
	{
		switch (selection)
		{
			case "seat_driver":
				return "pos_driver";
			case "seat_codriver":
				return "pos_codriver";
			case "seat_cargo1":
				return "pos_cargo1";
			case "seat_cargo2":
				return "pos_cargo2";
		}

		return "";
	}

	override void SetActions()
	{
		super.SetActions();

		AddAction(ActionRFOpenDoorOutside);
		AddAction(ActionRFCloseDoorOutside);
	}

	// колёса M1025, аккумулятор, свечи накала, фары и жидкости; дверей, капота и багажника-аттачментов у модели нет
	override void OnDebugSpawn()
	{
		SpawnUniversalParts();
		SpawnAdditionalItems();
		FillUpCarFluids();

		for (int i = 0; i < 4; i++)
			GetInventory().CreateInInventory("Offroad_02_Wheel");
	}
}

class RF_Humvee_Desert extends RF_Humvee {}

// «Открыть/Закрыть дверь» снаружи. Ванильные ActionCarDoorsOutside работают только с дверями-аттачментами
// (target — CarDoor), у нас же цель — сама машина, компонент двери seat_* в View Geometry.
class ActionRFDoorOutsideBase: ActionInteractBase
{
	protected bool m_RF_Open;

	void ActionRFDoorOutsideBase()
	{
		m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_OPENDOORFW;
		m_StanceMask = DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
	}

	override void CreateConditionComponents()
	{
		m_ConditionItem = new CCINone;
		m_ConditionTarget = new CCTCursor(UAMaxDistances.DEFAULT);
	}

	// источник анимации двери под курсором, "" — если смотрим не на дверь
	protected string RF_DoorSource(ActionTarget target)
	{
		RF_Humvee car = RF_Humvee.Cast(target.GetObject());
		if (!car)
			return "";

		TStringArray selections = new TStringArray;
		car.GetActionComponentNameList(target.GetComponentIndex(), selections);
		foreach (string selection : selections)
		{
			string source = car.GetAnimSourceFromSelection(selection);
			if (source != "")
				return source;
		}

		return "";
	}

	override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
	{
		if (player.GetCommand_Vehicle())
			return false;

		string source = RF_DoorSource(target);
		if (source == "")
			return false;

		bool isOpen = RF_Humvee.Cast(target.GetObject()).GetAnimationPhase(source) > 0.5;
		return isOpen != m_RF_Open;
	}

	override void OnStartServer(ActionData action_data)
	{
		string source = RF_DoorSource(action_data.m_Target);
		if (source == "")
			return;

		float phase = 0;
		if (m_RF_Open)
			phase = 1;

		RF_Humvee.Cast(action_data.m_Target.GetObject()).SetAnimationPhase(source, phase);
	}
}

class ActionRFOpenDoorOutside: ActionRFDoorOutsideBase
{
	void ActionRFOpenDoorOutside()
	{
		m_RF_Open = true;
		m_Text = "#open";
	}
}

class ActionRFCloseDoorOutside: ActionRFDoorOutsideBase
{
	void ActionRFCloseDoorOutside()
	{
		m_RF_Open = false;
		m_Text = "#close";
	}
}

modded class ActionConstructor
{
	override void RegisterActions(TTypenameArray actions)
	{
		super.RegisterActions(actions);

		actions.Insert(ActionRFOpenDoorOutside);
		actions.Insert(ActionRFCloseDoorOutside);
	}
}
