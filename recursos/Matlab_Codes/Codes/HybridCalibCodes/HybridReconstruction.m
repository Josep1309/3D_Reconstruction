function [X,Y,Z] = HybridReconstruction(Fy,fact,HybridModel1)

    phase = fact.*Fy;

    X = Eval_PhaseRegression(HybridModel1.coefx, phase);
    Y = Eval_PhaseRegression(HybridModel1.coefy, phase);
    Z = Eval_PhaseRegression(HybridModel1.coefz, phase);

end