function [coefx,coefy,coefz,erms,Nd] = HybridIterativeOpt(X,Y,Z,phases,mask,maskPF,ni,aa)
%%
% Funcion para realizar un ajuste Racional por optimización
% 
%
%

nposes = size(X,3); % Numero de posiciones del target
mask = (mask.*(~isnan(X)>0).*(~isnan(Y)>0).*(~isnan(Z)>0).*(~isnan(phases)>0))>0;
indi = NaN.*mask;
indi(mask) = 1;

X = X.*indi; Y = Y.*indi; Z = Z.*indi;
phases = phases.*indi;

figure(81), hold on
for j = 1:ni

    for i = 1:nposes

        x = X(:,:,i); y = Y(:,:,i); z = Z(:,:,i);
        indFit = mask(:,:,i);
        indFit2 = maskPF(:,:,i);
        
%         if (j==1)
%             aa2 = 20;
%             planesfig{i} = plot3(x(1:aa2:end), ...
%                                  y(1:aa2:end),z(1:aa2:end), ...
%                                  '.b','MarkerSize',2.5);
% 
% %             planesfig{i} = plot3(x, ...
% %                                  y,z, ...
% %                                  '.b','MarkerSize',2.5);
% 
% %             planesfig{i}.FaceColor = 'g';
% %             planesfig{i}.FaceAlpha = 0.2;
% %             planesfig{i}.EdgeColor = 'none';
% %             planesfig{i}.EdgeColor = 'g'; 
% %             planesfig{i}.EdgeAlpha = 0.3;
%         else
%             planesfig{i}.XData  = x(1:aa2:end);
%             planesfig{i}.YData  = y(1:aa2:end);
%             planesfig{i}.ZData  = z(1:aa2:end);
%             
%         end



        A= [x(indFit2(:)),y(indFit2(:)),ones(size(x(indFit2(:))))];
        AA = A'*A;
        B = A'*z(indFit2(:));
        TT = AA\B;
        co(1,:,i) = TT; % anadido


        % Old way - using perpendicular distance
        %         dis = (TT(1)*Xc+TT(2)*Yc-1*Zc+TT(3))/sqrt(TT(1)^2+TT(2)^2+1);
        dis = (TT(1)*x+TT(2)*y-1*z+TT(3))/sqrt(TT(1)^2+TT(2)^2+1);
        %dist{i} = dis;
        vt = [TT(1:2)' -1]/sqrt(TT(1)^2+TT(2)^2+1);
        %Xr{i} = [x,y,z];
        X(:,:,i) = x-vt(1)*dis;
        Y(:,:,i) = y-vt(2)*dis;
        Z(:,:,i) = z-vt(3)*dis;





%          if (j==1)
%             Idplanesfig{i} = surf(X(1:aa2:end,1:aa2:end,i),Y(1:aa2:end,1:aa2:end,i),Z(1:aa2:end,1:aa2:end,i));
%             Idplanesfig{i}.FaceColor = 'r';
%             Idplanesfig{i}.FaceAlpha = 0.5;
%             Idplanesfig{i}.EdgeColor = 'none';
% %             Idplanesfig{i}.EdgeColor = 'r'; 
%             Idplanesfig{i}.EdgeAlpha = 0;
%         else
%             Idplanesfig{i}.XData  = X(1:aa2:end,1:aa2:end);
%             Idplanesfig{i}.YData  = Y(1:aa2:end,1:aa2:end);
%             Idplanesfig{i}.ZData  = Z(1:aa2:end,1:aa2:end);
%         end


        vec=dis(indFit(:));
        erm = sqrt(sum((vec.^2)/numel(vec)));
        erms(j,i) =  erm;

    end


    % Calculo del vector normal espacial para cada pixel teniendo en cuenta
    % todos los puntos
    mag = sqrt(X.*X+Y.*Y+Z.*Z);
    ux = mean(X./mag,3,'omitnan');
    uy = mean(Y./mag,3,'omitnan');
    uz = mean(Z./mag,3,'omitnan');



    % Calculo de la longitud de cada vector basado en el vector unitario
    alpha = -co(1,3,:)./(co(1,1,:).*ux+co(1,2,:).*uy-uz);
    X = alpha.*ux;
    Y = alpha.*uy;
    Z = alpha.*uz;


    % Ajuste al modelo Racional
    [coefz,ez_rms,Nd] = Racionalfit3D(phases,Z,aa,1);
    [coefx,ex_rms] = Polyfit3D(Z,X,aa,0);
    [coefy,ey_rms] = Polyfit3D(Z,Y,aa,0);

%      [coefx,ex_rms] = Racionalfit3D(phases,X,aa,1); [coefy,ey_rms] = Racionalfit3D(phases,Y,aa,1);
%     Z = Eval_PhaseRegression(coefz,phases);

    % Evaluar el modelo Ajustado para obtener los nuevos puntos X,Y y Z
    Z = Eval_PhaseFrac(coefz,phases);
    X = Eval_PhaseRegression(coefx,Z);
    Y = Eval_PhaseRegression(coefy,Z);

%     X = Eval_PhaseFrac(coefx,phases); Y = Eval_PhaseFrac(coefy,phases);

    figure(91), imagesc(ez_rms), colorbar,% caxis([-0.2 0.2])
    figure(92), imagesc(ex_rms), colorbar,% caxis([-0.2 0.2])
    figure(93), imagesc(ey_rms), colorbar,% caxis([-0.2 0.2])
%     pause()
drawnow
end

end