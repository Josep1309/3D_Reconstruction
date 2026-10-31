function [meanRMS_e, coefx, coefy, coefz] = FunctionCostRecalib(coef,phases,pointsW)

% nposes = size(points,3);
% 
% X = points(:,:,:,1);
% Y = points(:,:,:,2);
% Z = points(:,:,:,3);
% coefz = Racionalfit3D(phases,Z,[],1);
% coefx = Polyfit3D(Z,X,[],1);
% coefy = Polyfit3D(Z,Y,[],1);

coefx = coef(:,:,1:2);
coefy = coef(:,:,3:4);
coefz = coef(:,:,5:7);


Zn = Eval_PhaseFrac(coefz,phases);
Xn = Eval_PhaseRegression(coefx,Zn);
Yn = Eval_PhaseRegression(coefy,Zn);

error = X*0; 

for i = 1:nposes

    Xaux = Xn(:,:,i); Xaux2 = pointsW(:,:,i,1);
    Yaux = Yn(:,:,i); Yaux2 = pointsW(:,:,i,2);
    Zaux = Zn(:,:,i); Zaux2 = pointsW(:,:,i,3);

    PointsM1 =  [Xaux(:) , Yaux(:) , Zaux(:) ];
    PointsM2 =  [Xaux2(:), Yaux2(:), Zaux2(:)];
    
    index = 1:100:size(PointsM1,1); 

    [tformEst,inlierIndex] = estimateGeometricTransform3D(PointsM1(index,:), PointsM2(index,:),'rigid','MaxDistance',0.3); 
    PointM2_est = transformPointsForward(tformEst,PointsM1);

    errorrms = rms(vecnorm(PointM2_est-PointsM2,2,2));


    error(:,:,i) = reshape(errorrms,size(error,[1 2]));
    
end

meanRMS_e = mean(error,3);


end