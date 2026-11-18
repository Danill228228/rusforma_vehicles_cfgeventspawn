// Машина с люком на крыше. Состояние люка = фаза источника анимации "HatchRoof"
// (source = "user" в config.cpp, синхронизируется с клиентами движком) и сохраняется в БД сервера.

class RF_Humvee extends OffroadHatchback
{
	static const string HATCH_SOURCE = "HatchRoof";
	static const string HATCH_SELECTION = "hatch_roof";

	protected bool m_RF_HatchOpen;

	override void SetActions()
	{
		super.SetActions();

		AddAction(ActionRFOpenHatchInVehicle);
		AddAction(ActionRFCloseHatchInVehicle);
		AddAction(ActionRFOpenHatchOutside);
		AddAction(ActionRFCloseHatchOutside);
	}

	bool RF_IsHatchOpen()
	{
		return GetAnimationPhase(HATCH_SOURCE) > 0.5;
	}

	// Вызывать только на сервере.
	void RF_SetHatchOpen(bool open)
	{
		m_RF_HatchOpen = open;

		float phase = 0;
		if (open)
			phase = 1;

		SetAnimationPhase(HATCH_SOURCE, phase);
	}

	void RF_ToggleHatch()
	{
		RF_SetHatchOpen(!RF_IsHatchOpen());
	}

	// Люк — ещё один путь в салон: открытый люк не мешает стрельбе/обзору пассажира сзади.
	// При желании можно разрешить выход через люк, переопределив CrewCanGetThrough().

	override void OnStoreSave(ParamsWriteContext ctx)
	{
		super.OnStoreSave(ctx);
		ctx.Write(m_RF_HatchOpen);
	}

	override bool OnStoreLoad(ParamsReadContext ctx, int version)
	{
		if (!super.OnStoreLoad(ctx, version))
			return false;

		if (!ctx.Read(m_RF_HatchOpen))
			m_RF_HatchOpen = false;

		return true;
	}

	override void AfterStoreLoad()
	{
		super.AfterStoreLoad();
		RF_SetHatchOpen(m_RF_HatchOpen);
	}
}

class RF_Humvee_Desert extends RF_Humvee {}
