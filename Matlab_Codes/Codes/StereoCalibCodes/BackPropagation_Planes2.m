function [Xc,Yc,Zc,Up,Vp] = BackPropagation_Planes2(stereo_params,typeStereo,Rot_mat,Trans_vec,cam_size,vis)
%%
% Calcula las coordenadas Xc,Yc,Zc de un plano de calibración teniendo en
% cuenta las transformaciones rigidas y las coordenadas en el plano imagen
% del proyectos con coordendas Up, Vp
% input:
%   Stereo_params: Parametros de calibración estereo del sistema
%   Rot_mat: Matrices de rotacion de los planos respecto a la cam
%   Trans_vec: Vectores de traslacion de los planos respecto a la cam
%   cam_size: Tamaño del sensor de la camara en pixeles
%
% Output:
%   (Xc,Yc,Zc): Coordenadas del plano respecto a la cam para cada pixe (uc, vc)
%   (Up, Vc): Coordenadas del plano proyectado sobre el proyector
%
%
%% Camera-projector and intrinsic parameters
if(strcmp(typeStereo,'BT'))
    K1 = stereo_params.KK_left;
    K2 = stereo_params.KK_right;
    Rp = stereo_params.R;
    tp = stereo_params.T;
    k1 = stereo_params.kc_left;
    k2 = stereo_params.kc_right;
elseif(strcmp(typeStereo,'MT'))
    K1 = stereo_params.CameraParameters1.IntrinsicMatrix';
    K2 = stereo_params.CameraParameters2.IntrinsicMatrix';

    Rp = stereo_params.RotationOfCamera2';
    tp = stereo_params.TranslationOfCamera2';
    
    if(stereo_params.CameraParameters1.RadialDistortion<3)
        k1 =  [stereo_params.CameraParameters1.RadialDistortion(1:2) stereo_params.CameraParameters1.TangentialDistortion 0];
    else
        k1 =  [stereo_params.CameraParameters1.RadialDistortion(1:2) stereo_params.CameraParameters1.TangentialDistortion stereo_params.CameraParameters1.RadialDistortion(3)];
    end

    if(stereo_params.CameraParameters2.RadialDistortion<3)
        k2 =  [stereo_params.CameraParameters2.RadialDistortion(1:2) stereo_params.CameraParameters2.TangentialDistortion 0];
    else
        k2 =  [stereo_params.CameraParameters2.RadialDistortion(1:2) stereo_params.CameraParameters2.TangentialDistortion stereo_params.CameraParameters2.RadialDistortion(3)];
    end
end



% Page transpose to transpose all pages of R(:,:,nPoses)
R = Rot_mat;
t = Trans_vec;

% Distortion coefficients

colors = [0    0.4471    0.7412;    0.4667    0.6745    0.1882
    0.8510    0.3255    0.0980;    0.8510    0.3255    0.0980;
    0.3020    0.7451    0.9333;    0.4941    0.1843    0.5569
    0.9294    0.6941    0.1255;    0.4941    0.1843    0.5569
    0.6353    0.0784    0.1843;    0.9294    0.6941    0.1255
    0         0.4471    0.7412;    0.4667    0.6745    0.1882
    0.8510    0.3255    0.0980;    0.8510    0.3255    0.0980;
    0.3020    0.7451    0.9333;    0.4941    0.1843    0.5569
    0.9294    0.6941    0.1255;    0.4941    0.1843    0.5569
    0.6353    0.0784    0.1843;    0.9294    0.6941    0.1255
    0         0.4471    0.7412;    0.4667    0.6745    0.1882
    0.8510    0.3255    0.0980;    0.8510    0.3255    0.0980;
    0.3020    0.7451    0.9333;    0.4941    0.1843    0.5569
    0.9294    0.6941    0.1255;    0.4941    0.1843    0.5569
    0.6353    0.0784    0.1843;    0.9294    0.6941    0.1255
    0         0.4471    0.7412;    0.4667    0.6745    0.1882
    0.8510    0.3255    0.0980;    0.8510    0.3255    0.0980;
    0.3020    0.7451    0.9333;    0.4941    0.1843    0.5569
    0.9294    0.6941    0.1255;    0.4941    0.1843    0.5569
    0.6353    0.0784    0.1843;    0.9294    0.6941    0.1255];

%%

nPoses = size(Rot_mat,3);

a = 1;
[u,v] = meshgrid(1:a:cam_size(2),1:a:cam_size(1));
u = u(:);  v = v(:);

% Cam distortion compensation
aux = K1\[u';v';v'*0+1];
aux = aux./aux(3,:);
[x] = comp_distortion_oulu(aux(1:2,:),k1);
u = x(1,:); v = x(2,:);


% 3D coordinates Initialization
Xc = zeros([cam_size nPoses]); Yc = Xc; Zc = Xc;

% Theorical projection on the projector' image plane 
Up = Xc; Vp = Xc;


for k=1:nPoses

    % Extrinsic poses of the planes
    M = (R(:,:,k));   P = (t(:,k));

    %     We solved algebraically
    x_w = ((M(1,2)*P(2) - M(2,2)*P(1) + M(2,2)*P(3)*u - M(3,2)*P(2)*u - M(1,2)*P(3)*v + M(3,2)*P(1)*v)./(M(1,1)*M(2,2) - M(1,2)*M(2,1) + M(2,1)*M(3,2)*u - M(2,2)*M(3,1)*u - M(1,1)*M(3,2)*v + M(1,2)*M(3,1)*v));
    y_w = (-(M(1,1)*P(2) - M(2,1)*P(1) + M(2,1)*P(3)*u - M(3,1)*P(2)*u - M(1,1)*P(3)*v + M(3,1)*P(1)*v)./(M(1,1)*M(2,2) - M(1,2)*M(2,1) + M(2,1)*M(3,2)*u - M(2,2)*M(3,1)*u - M(1,1)*M(3,2)*v + M(1,2)*M(3,1)*v));


    % 3D coordinates of the board (plane) view from the camera
    X_c = R(:,:,k) * [x_w(:), y_w(:), zeros(size(y_w(:)))]' + t(:,k); 

    Xc(:,:,k) = reshape(X_c(1,:),cam_size);
    Yc(:,:,k) = reshape(X_c(2,:),cam_size);
    Zc(:,:,k) = reshape(X_c(3,:),cam_size);


    aa = 50;
    if(vis==1)
        figure(2), hold on
        if(strcmp(typeStereo,'MT') && k==1)
%             showExtrinsics(stereo_params), %pause()

        end
        g2 = surf( Yc([1 end],[1 end],k), Zc([1 end],[1 end],k),Xc([1 end],[1 end],k));
%         g2 = surf( Xc(1:aa:end,1:aa:end,k), Zc(1:aa:end,1:aa:end,k), Yc(1:aa:end,1:aa:end,k));
        g2.FaceColor = colors(k,:);
        g2.EdgeColor = colors(k,:)/2;
        g2.FaceAlpha = 0.38;
        g2.EdgeAlpha = 1;

%         g2.LineStyle ='None';
%         set(g2, 'DataAspectRatio', [1, 1, 1])
%         axis equal;
%         view(90, 90);
%         scatter3(X_c(1, 1:aa:end), X_c(3, 1:aa:end), X_c(2, 1:aa:end),'.');
    end

    % Theorical Phase
    X_p = [Rp tp]*[X_c; X_c(1,:)*0+1];
    X_p = X_p./X_p(3,:);
    u_p = X_p(1,:); v_p = X_p(2,:);


    % Apply distortion when the points are projected to projector's image plane
    aux = [u_p;v_p];
    [x] = apply_distortion(aux,k2);
    aux = K2*[x; x(1,:)*0+1];
    aux = aux./aux(3,:);
    u_p = aux(1,:); v_p = aux(2,:);


    % Pixel coordinates of the board points on the projector image plane
    Up(:,:,k) = reshape(u_p(:)',cam_size);
    Vp(:,:,k) = reshape(v_p(:)',cam_size);


end

end