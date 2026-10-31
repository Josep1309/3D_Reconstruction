function [coefx,coefy,coefz,erms] = HybridIterativeOptWithFeatures(X,Y,Z,phases,cp,mask,ni,aa)


nposes = size(X,3);
mask = (mask.*(~isnan(X)>0).*(~isnan(Y)>0).*(~isnan(Z)>0).*(~isnan(phases)>0))>0;
indi = NaN.*mask;
indi(mask) = 1;

X = X.*indi;
Y = Y.*indi;
Z = Z.*indi;
phases = phases.*indi;

ranX = shiftdim(max(X,[],[1 2]) - min(X,[],[1 2]));
ranY = shiftdim(max(Y,[],[1 2]) - min(Y,[],[1 2]));
ranZ = shiftdim(max(Z,[],[1 2]) - min(Z,[],[1 2]));

d = sqrt(ranX.*ranX+ranY.*ranY+ranZ.*ranZ);
[~,in] = max(d);

for j = 1:ni

    for i = 1:nposes
        x = X(:,:,i);
        y = Y(:,:,i);
        z = Z(:,:,i);
        indFit = mask(:,:,i);


        A= [x(indFit(:)),y(indFit(:)),ones(size(x(indFit(:))))];
        AA = A'*A;
        B = A'*z(indFit(:));
        TT = AA\B;
        co(i,:) = TT; % anadido


        % Old way - using perpendicular distance
        %         dis = (TT(1)*Xc+TT(2)*Yc-1*Zc+TT(3))/sqrt(TT(1)^2+TT(2)^2+1);
        dis = (TT(1)*x+TT(2)*y-1*z+TT(3))/sqrt(TT(1)^2+TT(2)^2+1);
        %dist{i} = dis;
        vt = [TT(1:2)' -1]/sqrt(TT(1)^2+TT(2)^2+1);
        %Xr{i} = [x,y,z];
        X(:,:,i) = x-vt(1)*dis;
        Y(:,:,i) = y-vt(2)*dis;
        Z(:,:,i) = z-vt(3)*dis;


        vec=dis(indFit(:));
        erm = sqrt(sum((vec.^2)/numel(vec)));
        erms(j,i) =  erm;

    end

    [coefz,ez_rms] = Racionalfit3D(phases,Z,aa,1);
%     [coefz,ez_rms] = Polyfit3D(phases,Z,aa,3);
    [coefx,ex_rms] = Polyfit3D(Z,X,aa,0);
    [coefy,ey_rms] = Polyfit3D(Z,Y,aa,0);

%      [coefx,ex_rms] = Racionalfit3D(phases,X,aa,1); [coefy,ey_rms] = Racionalfit3D(phases,Y,aa,1);

%     Z = Eval_PhaseRegression(coefz,phases);
    Z = Eval_PhaseFrac(coefz,phases);
    X = Eval_PhaseRegression(coefx,Z);
    Y = Eval_PhaseRegression(coefy,Z);

%     X = Eval_PhaseFrac(coefx,phases); Y = Eval_PhaseFrac(coefy,phases);

    figure(91), imagesc(ez_rms), colorbar,% caxis([-0.2 0.2])
    figure(92), imagesc(ex_rms), colorbar,% caxis([-0.2 0.2])
    figure(93), imagesc(ey_rms), colorbar,% caxis([-0.2 0.2])
    pause()

end

end