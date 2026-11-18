// Машина: посадка экипажа, анимации сидений, камера.
// Скрипт наследует OffroadHatchback (как и config.cpp): оттуда аккумулятор как источник питания, звуки двигателя, фары, гудок.
// Действия с люком добавляет отдельный аддон RF_Humvee_Hatch (modded class RF_Humvee).

class RF_Humvee extends OffroadHatchback
{
	override int GetAnimInstance()
	{
		return VehicleAnimInstances.HATCHBACK;
	}

	override float GetTransportCameraDistance()
	{
		return 5.5;
	}

	override vector GetTransportCameraOffset()
	{
		return "0 1.6 0";
	}

	override int GetSeatAnimationType(int posIdx)
	{
		switch (posIdx)
		{
			case 0:
				return DayZPlayerConstants.VEHICLESEAT_DRIVER;
			case 1:
				return DayZPlayerConstants.VEHICLESEAT_CODRIVER;
			case 2:
				return DayZPlayerConstants.VEHICLESEAT_PASSENGER_L;
			case 3:
				return DayZPlayerConstants.VEHICLESEAT_PASSENGER_R;
		}

		return 0;
	}

	// Двери — анимированные части кузова, не аттачменты. Состояние двери = фаза её источника анимации,
	// тогда ванильные «Открыть/Закрыть» из салона (ActionOpenCarDoors) работают через эти методы.
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
		}

		return "";
	}

	override string GetDoorSelectionNameFromSeatPos(int posIdx)
	{
		switch (posIdx)
		{
			case 0:
				return "doors_driver";
			case 1:
				return "doors_codriver";
			case 2:
				return "doors_cargo1";
			case 3:
				return "doors_cargo2";
		}

		return "";
	}

	// «Слот» двери для GetCarDoorsState: у нас это имя источника анимации
	override string GetDoorInvSlotNameFromSeatPos(int posIdx)
	{
		return GetAnimSourceFromSelection(GetDoorSelectionNameFromSeatPos(posIdx));
	}

	override int GetCarDoorsState(string slotType)
	{
		if (GetSeatIndexFromDoor(slotType) == -1)
			return CarDoorState.DOORS_MISSING;

		return TranslateAnimationPhaseToCarDoorState(slotType);
	}

	// Как у ванили: сесть и выйти можно только через открытую дверь.
	override bool CrewCanGetThrough(int posIdx)
	{
		return GetCarDoorsState(GetDoorInvSlotNameFromSeatPos(posIdx)) != CarDoorState.DOORS_CLOSED;
	}

	override void SetActions()
	{
		super.SetActions();

		AddAction(ActionRFOpenDoorOutside);
		AddAction(ActionRFCloseDoorOutside);
	}

	// Где надо стоять, чтобы сесть (ActionGetInTransport -> CanReachSeatFromDoors). Ада ищет seat_con_*,
	// в нашей модели у дверей стоят pos_*: без этого действие «Сесть» не появляется.
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

	override bool CanReachSeatFromSeat(int currentSeat, int nextSeat)
	{
		return true;
	}

	override bool CanReachDoorsFromSeat(string pDoorsSelection, int pCurrentSeat)
	{
		return true;
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
