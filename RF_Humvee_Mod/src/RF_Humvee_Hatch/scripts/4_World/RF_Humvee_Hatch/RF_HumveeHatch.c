// Люк на крыше. Положение люка = фаза источника анимации "HatchRoof"
// (source = "user" в config.cpp RF_Humvee — движок сам синхронизирует её с клиентами).

modded class RF_Humvee
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

// Без регистрации здесь AddAction() не найдёт действия.
modded class ActionConstructor
{
	override void RegisterActions(TTypenameArray actions)
	{
		super.RegisterActions(actions);

		actions.Insert(ActionRFOpenHatchInVehicle);
		actions.Insert(ActionRFCloseHatchInVehicle);
		actions.Insert(ActionRFOpenHatchOutside);
		actions.Insert(ActionRFCloseHatchOutside);
	}
}
