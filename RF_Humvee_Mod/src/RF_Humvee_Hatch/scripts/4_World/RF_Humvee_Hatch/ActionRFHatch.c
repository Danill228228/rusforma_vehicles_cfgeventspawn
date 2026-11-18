// Действия «Открыть люк» / «Закрыть люк».
//  * InVehicle — из салона (любое место), без цели, как переключение фар.
//  * Outside   — снаружи, когда игрок смотрит на крышку люка (селекция "hatch_roof"
//                должна быть в View Geometry / Fire Geometry как отдельный компонент).

RF_Humvee RF_GetHumveeFromVehicle(PlayerBase player)
{
	if (!player)
		return null;

	HumanCommandVehicle vehCommand = player.GetCommand_Vehicle();
	if (!vehCommand)
		return null;

	return RF_Humvee.Cast(vehCommand.GetTransport());
}

// ------------------------------------------------------------------ из салона
class ActionRFHatchInVehicleBase: ActionInteractBase
{
	protected bool m_RF_WantOpen;

	void ActionRFHatchInVehicleBase()
	{
		m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_HEADLIGHT;
		m_StanceMask = DayZPlayerConstants.STANCEMASK_ALL;
	}

	override void CreateConditionComponents()
	{
		m_ConditionItem = new CCINone;
		m_ConditionTarget = new CCTNone;
	}

	override bool HasTarget()
	{
		return false;
	}

	override bool CanBeUsedInVehicle()
	{
		return true;
	}

	override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
	{
		RF_Humvee car = RF_GetHumveeFromVehicle(player);
		if (!car)
			return false;

		return car.RF_IsHatchOpen() != m_RF_WantOpen;
	}

	override void OnStartServer(ActionData action_data)
	{
		RF_Humvee car = RF_GetHumveeFromVehicle(action_data.m_Player);
		if (car)
			car.RF_SetHatchOpen(m_RF_WantOpen);
	}
}

class ActionRFOpenHatchInVehicle: ActionRFHatchInVehicleBase
{
	void ActionRFOpenHatchInVehicle()
	{
		m_RF_WantOpen = true;
		m_Text = "Открыть люк";
	}
}

class ActionRFCloseHatchInVehicle: ActionRFHatchInVehicleBase
{
	void ActionRFCloseHatchInVehicle()
	{
		m_RF_WantOpen = false;
		m_Text = "Закрыть люк";
	}
}

// ------------------------------------------------------------------ снаружи
class ActionRFHatchOutsideBase: ActionInteractBase
{
	protected bool m_RF_WantOpen;

	void ActionRFHatchOutsideBase()
	{
		m_CommandUID = DayZPlayerConstants.CMD_ACTIONMOD_OPENDOORFW;
		m_StanceMask = DayZPlayerConstants.STANCEMASK_CROUCH | DayZPlayerConstants.STANCEMASK_ERECT;
	}

	override void CreateConditionComponents()
	{
		m_ConditionItem = new CCINone;
		m_ConditionTarget = new CCTCursor(UAMaxDistances.DEFAULT);
	}

	protected RF_Humvee GetCar(ActionTarget target)
	{
		if (!target)
			return null;

		RF_Humvee car = RF_Humvee.Cast(target.GetObject());
		if (!car)
			car = RF_Humvee.Cast(target.GetParent());

		return car;
	}

	override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
	{
		if (player.GetCommand_Vehicle())
			return false;

		RF_Humvee car = GetCar(target);
		if (!car)
			return false;

		string selection = car.GetActionComponentName(target.GetComponentIndex());
		if (selection != RF_Humvee.HATCH_SELECTION)
			return false;

		return car.RF_IsHatchOpen() != m_RF_WantOpen;
	}

	override void OnStartServer(ActionData action_data)
	{
		RF_Humvee car = GetCar(action_data.m_Target);
		if (car)
			car.RF_SetHatchOpen(m_RF_WantOpen);
	}
}

class ActionRFOpenHatchOutside: ActionRFHatchOutsideBase
{
	void ActionRFOpenHatchOutside()
	{
		m_RF_WantOpen = true;
		m_Text = "Открыть люк";
	}
}

class ActionRFCloseHatchOutside: ActionRFHatchOutsideBase
{
	void ActionRFCloseHatchOutside()
	{
		m_RF_WantOpen = false;
		m_Text = "Закрыть люк";
	}
}
