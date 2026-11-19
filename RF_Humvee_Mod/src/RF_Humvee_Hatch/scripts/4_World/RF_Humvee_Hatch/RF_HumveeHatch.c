// Люк на крыше: действия и сохранение положения. Состояние m_RF_HatchOpen и деталь люка — в основном аддоне
// (RF_Humvee.RF_SetHatchOpen передаёт его клиентам).

modded class RF_Humvee
{
	override void SetActions()
	{
		super.SetActions();

		AddAction(ActionRFOpenHatchInVehicle);
		AddAction(ActionRFCloseHatchInVehicle);
		AddAction(ActionRFOpenHatchOutside);
		AddAction(ActionRFCloseHatchOutside);
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
