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

	// Дверей-аттачментов нет (они часть кузова), поэтому сесть/выйти можно всегда.
	override bool CrewCanGetThrough(int posIdx)
	{
		return true;
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
