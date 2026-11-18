// Машина: посадка экипажа, анимации сидений, камера.
// Действия с люком добавляет отдельный аддон RF_Humvee_Hatch (modded class RF_Humvee).

class RF_Humvee extends CarScript
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
