function [XcM,YcM,ZcM,t1] = StereoReconstruction_points(Uc,Vc,fx,fy,FringePitch,stereoParams,typeCalib,Fd)
%%
% Fases : Fases de los objetos a reconstruir por medio de calibracion
%          stereo
% Mask : Mascara de los objetos que se desean reconstruir
% FringePitch : Paso de las franjas proyectadas.
% StereoParams: Parametros estereos del sistema.
% typeCalib: Tipo de calibración estereo: 
%           1: ToolboxBouguet. 2:Parametros por vector. 3: Toolbox matlab
% Fd: Fase utilizada para la triangulación. 
%           'Fx': Utilizacion de fase con variación en la direccion u
%           'Fy': Utilizacion de fase con variación en la direccion v
% [XcM,YcM,ZcM]: Coordenadas tridimensionales obtenidas de la triangulación
%                estereo. 
%

% Determinación del tipo de parametros estereos que se están ingresando:
if(typeCalib==1)
    Ac = stereoParams.KK_left;
    Ap = stereoParams.KK_right;
    W = [stereoParams.R,stereoParams.T];
    Kr1 = [stereoParams.kc_left(1),stereoParams.kc_left(2), stereoParams.kc_left(5)];
    Kt1 = stereoParams.kc_left(3:4)';
    Kr2 = [stereoParams.kc_right(1) stereoParams.kc_right(2) stereoParams.kc_right(5)];
    Kt2 =  stereoParams.kc_right(3:4)';
     offset = 0;
elseif(typeCalib==2)

%     params0 = [s.KK_left([1 5 4 7 8]),s.kc_left',s.KK_right([1 5 4 7 8]),s.kc_right',s.om',s.T'];

    Ac = [stereoParams(1) stereoParams(3) stereoParams(4);
        0               stereoParams(2) stereoParams(5);
        0                     0               1           ];
    Kr1 = stereoParams([6 7 10]);
    Kt1 = stereoParams([8 9]);

    Ap = [stereoParams(11) stereoParams(13) stereoParams(14);
        0                stereoParams(12) stereoParams(15);
        0                     0               1           ];
    Kr2 = stereoParams([16 17 20]);
    Kt2 = stereoParams([18 19]);
    W = [rodrigues(stereoParams(21:23)),stereoParams(24:26)'];
    if(numel(stereoParams)==27)
        offset = stereoParams(27);
    else
        offset = 0;
    end
elseif(typeCalib==3)
    Ac = stereoParams.CameraParameters1.IntrinsicMatrix';
    Ap = stereoParams.CameraParameters2.IntrinsicMatrix';
    W = [stereoParams.RotationOfCamera2;stereoParams.TranslationOfCamera2]';
    Kr1 = stereoParams.CameraParameters1.RadialDistortion;
    Kt1 = stereoParams.CameraParameters1.TangentialDistortion;
    Kr2 = stereoParams.CameraParameters2.RadialDistortion;
    Kt2 = stereoParams.CameraParameters2.TangentialDistortion;
    offset = 0;
end

% Puntos= NaN.*ones([size(Mask,1),size(Mask,2),size(Mask,3),3]);
% Pc = [eye(3) zeros(3,1)]; %Pc=Pc/Pc(end,end);

% [Uc,Vc]=meshgrid(1:size(fx(:,:,1),2),1:size(fx(:,:,1),1));

Mask = Uc*0+1;

Uc = Uc(:); Vc = Vc(:);
rc = (Ac)\([Uc(:),Vc(:),Uc(:)*0+1]');

fprintf('.')
% fprintf(' Compensando distorsiones de la Camara ...  Coeficientes [%d,%d,%d,%d,%d] \n',[Kr1(1:2),Kt1,Kr1(3)]);
% rc = comp_distortion_oulu(xd(1:2,:),[Kr1(1:2),Kt1,Kr1(3)]);

ta1 = tic;
if(sum([Kr1(1:2),Kt1,Kr1(3)])==0)
    rc = rc(1:2,:);
else
    rc = comp_distortion_oulu(rc(1:2,:),[Kr1(1:2),Kt1,Kr1(3)]);
end
% fprintf('\n ... Distorsiones compensadas ... \n ');


Ud = reshape(rc(1,:),size(fx));
Vd = reshape(rc(2,:),size(fx));

Ud = Ud(:);
Vd = Vd(:);

% Vector de direccion con distorsion corregida
rui =[Ud';Vd';Vd'.^0];
clear Ud Vd


% Conversión Fase a coordenadas proyector:
Fx = fx(:);
Fy = fy(:);
up = FringePitch*Fx/(2*pi);
vp = FringePitch*Fy/(2*pi);

% Vector de coordenadas normalizadas
x = (Ap- [0 0 0;0 0 offset;0 0 0])\([up(:),vp(:),up(:)*0+1]');
clear up vp

fprintf('.')
% fprintf(1,' Compensando distorsiones del proyector ...  Coeficientes [%d,%d,%d,%d,%d] \n',[Kr2(1:2),Kt2,Kr2(3)]);
if(sum([Kr2(1:2),Kt2,Kr2(3)])==0)
    x = x(1:2,:);
else
    [x] = comp_distortion_oulu(x(1:2,:),[Kr2(1:2),Kt2,Kr2(3)]);
end

if (offset~=0)
    x = (Ap - [0 0 0;0 0 offset;0 0 0])*[x;x(1,:)*0+1];
    x = Ap\x;
    x = x(1:2,:)./x(3,:);
end

% fprintf('\n Distorsiones compensadas \n')
% Seleccion de los coeficientes de triangulación dependiendo de la
% direccion de fase utilizada para reconstruir

if(strcmp(Fd,'Fx'))
    A =  W(1,1)-W(3,1)* x(1,:);
    B =  W(1,2)-W(3,2)* x(1,:);
    C =  W(1,3)-W(3,3)* x(1,:);
    D = -W(1,4)+W(3,4)* x(1,:);
elseif(strcmp(Fd,'Fy'))
    A =  W(2,1)-W(3,1)* x(2,:);
    B =  W(2,2)-W(3,2)* x(2,:);
    C =  W(2,3)-W(3,3)* x(2,:);
    D = -W(2,4)+W(3,4)* x(2,:);
end


Zc=D./(A.*(rui(1,:))+B.*(rui(2,:))+C);
clear A B C D
Xc = Zc.*rui(1,:);
Yc = Zc.*rui(2,:);

t1=toc(ta1); %t2=toc(ta2); t3=toc(ta3);

XcM = fx*NaN; XcM(Mask>0) =  Xc;
YcM = fx*NaN; YcM(Mask>0) =  Yc;
ZcM = fx*NaN; ZcM(Mask>0) =  Zc;

fprintf('.')
% fprintf(1,' Reconstrucion completa ... \n');

end