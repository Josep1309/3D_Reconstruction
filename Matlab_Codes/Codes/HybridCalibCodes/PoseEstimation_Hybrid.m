function [erms,dist,Xi,Xr,co] = PoseEstimation_Hybrid(params,X,StereoType,Fd,indFit)
 %% 
 %
 % Parametros de entrada: 
 % params: parametros estereos ordenados de la siguiente forma: 
 %
 %  params(1)= fx_c  ;    params(2) = fy_c;
 %  params(3) =skew_c ;    params(4)   =cx_c;
 %  params(5)   =cy_c ;   params(6)   = k1_c;
 %  params(7)   =k2_c;    params(8)  =p1_c ;
 %  params(9)   = p2_c;    params(10) = k3_c ;
 %  
 %  params(11)   = fx_p;    params(12)  =fy_p;
 %  params(13= skew_p );    params(14) = cx_p;
 %  params(15) =cy_p  ;    params(16) = k1_p;
 %  params(17)  = k2_p;    params(18)= p1_p ;
 %  params(19)  = p2_p;     params(20)= k3_p;
 %  
 %  params(21:23)= om;    params(24:26)= T;
 
 % X: es una celda de tamaño M, donde se encuentran almacenadas M matrices, 
 % donde M hace referencia a las posiciones del plano, las
 % cuales tienen un tamaño de 4XN, se almacenan las coordenadas camara y
 % proyector.
 %
 % Parametros de salida:
 % erms: Errores RMS de los puntos a un plano ideal
 % dist: Los errores de ajuste de cada punto a cada plano
 % Xi: Las coordenadas ideales de cada punto reconstruido para que caiga en
 % el plano
 % Xr: Coordenadas reconstruidas del plano por la tecnica de visión estereo
    
 if(strcmp(StereoType,'BT'))
    s = params;
    Ac = s.KK_left;
    Ap = s.KK_right;
    Tp = [s.R,s.T];
    Kr1 = [s.kc_left(1),s.kc_left(2), s.kc_left(5)];
    Kt1 = s.kc_left(3:4)';
    Kr2 = [s.kc_right(1) s.kc_right(2) s.kc_right(5)];
    Kt2 =  s.kc_right(3:4)';
elseif(strcmp(StereoType,'XX'))
    
    fx_c   = params(1);   fy_c   = params(2);
    skew_c = params(3);   cx_c   = params(4);
    cy_c   = params(5);   k1_c   = params(6);
    k2_c   = params(7);   p1_c   = params(8);
    p2_c   = params(9);   k3_c   = params(10);
    
    fx_p   = params(11);  fy_p   = params(12);
    skew_p = params(13);  cx_p   = params(14);
    cy_p   = params(15);  k1_p   = params(16);
    k2_p   = params(17);  p1_p   = params(18);
    p2_p   = params(19);  k3_p   = params(20);
    
    om = params(21:23);   T = params(24:26);
    Ac = [fx_c skew_c cx_c;0 fy_c cy_c;0 0 1];
    Ap = [fx_p skew_p cx_p;0 fy_p cy_p;0 0 1];
    Kr1= [k1_c,k2_c, k3_c];
    Kt1= [p1_c,p2_c];
    Kr2= [k1_p,k2_p, k3_p];
    Kt2= [p1_p,p2_p];
    Tp = [rodrigues(om) T'];
 elseif(strcmp(StereoType,'MT'))
     Ac =  params.CameraParameters1.IntrinsicMatrix';
     Ap =  params.CameraParameters2.IntrinsicMatrix';
     Kr1= params.CameraParameters1.RadialDistortion;
     Kt1= params.CameraParameters1.TangentialDistortion;

     Kr2= params.CameraParameters2.RadialDistortion;
     Kt2= params.CameraParameters2.TangentialDistortion;

     if(numel(Kr1)<3)
        Kr1(3)=0;
     end
     if(numel(Kr2)<3)
        Kr2(3)=0;
     end
     

     Tp = [params.RotationOfCamera2' params.TranslationOfCamera2'];
    
 end
    


    W = Tp;
    erms = 0;
    Xi={}; Xr={};
    for i=1:size(X,2)

%         IndexFit = indFit{i};
        tic
        uc = X{i}(:,1);
        vc = X{i}(:,2);
        up = X{i}(:,3);
        vp = X{i}(:,4);
        
        xd = (Ac^-1)*([uc(:),vc(:),uc(:).^0]');
        %     fprintf(' Compensando distorsiones de la Camara ...  Coeficientes [%d,%d,%d,%d,%d] \n',[Kr1(1:2),Kt1,Kr1(3)]);
        
        if(sum([Kr1(1:2),Kt1,Kr1(3)])==0)
            rc = xd(1:2,:);
        else
            rc = comp_distortion_oulu(xd(1:2,:),[Kr1(1:2),Kt1,Kr1(3)]);
        end
        
        ru =[rc;rc(1,:).^0];
        
        
        xd = Ap\([up(:),vp(:),up(:).^0]');
        %     fprintf(1,' Compensando distorsiones del proyector ...  Coeficientes [%d,%d,%d,%d,%d] \n',[Kr2(1:2),Kt2,Kr2(3)]);
        if(sum([Kr2(1:2),Kt2,Kr2(3)])==0)
            x = xd(1:2,:);
        else
            [x] = comp_distortion_oulu(xd(1:2,:),[Kr2(1:2),Kt2,Kr2(3)]);
        end
        
        if(strcmp(Fd,'Fx'))
            mx = x(1,:);
            rui=ru;

            %     fprintf(1,' Realizando la triangulacion ... \n');
            A =  W(1,1)-W(3,1)*mx;
            B =  W(1,2)-W(3,2)*mx;
            C =  W(1,3)-W(3,3)*mx;
            D = -W(1,4)+W(3,4)*mx;
        elseif(strcmp(Fd,'Fy'))
            mx = x(2,:);
            rui=ru;
            %     fprintf(1,' Realizando la triangulacion ... \n');
            A =  W(2,1)-W(3,1)*mx;
            B =  W(2,2)-W(3,2)*mx;
            C =  W(2,3)-W(3,3)*mx;
            D = -W(2,4)+W(3,4)*mx;
        end

        
        Zc=  D./(A.*(rui(1,:)./rui(3,:))+B.*(rui(2,:)./rui(3,:))+C);
        Xc = Zc.*rui(1,:)./rui(3,:);
        Yc = Zc.*rui(2,:)./rui(3,:);
        
        
        
        %     fprintf(1,' Reconstrucion completa ... \n');
        

        x = Xc(:); y = Yc(:); z = Zc(:); 

%         x = Xc(indFit{i}); y = Yc(indFit{i}); z = Zc(indFit{i});



        A= [x(indFit{i}),y(indFit{i}),ones(size(x(indFit{i})))];
        AA = A'*A;
        B = A'*z(indFit{i});
        TT = AA\B;
        
        co(i,:) = TT; % anadido

        % Old way - using perpendicular distance
%         dis = (TT(1)*Xc+TT(2)*Yc-1*Zc+TT(3))/sqrt(TT(1)^2+TT(2)^2+1);
        dis = (TT(1)*x+TT(2)*y-1*z+TT(3))/sqrt(TT(1)^2+TT(2)^2+1);
        dist{i} = dis;
        vt = [TT(1:2)' -1]/sqrt(TT(1)^2+TT(2)^2+1);
        Xr{i} = [x,y,z];
        Xi{i} = [x-vt(1)*dis,y-vt(2)*dis,z-vt(3)*dis];

        
%         % New way using the vector scaling factor alpha
%         alpha = abs(TT(3)./(TT(1)*x+TT(2)*y-1*z));
%         Xi{i} = [alpha.*x alpha.*y alpha.*z];
%         
%         dis = sqrt((alpha.*x - x).^2 + (alpha.*y - y).^2 + (alpha.*z - z).^2);
%         dist{i} = dis;
        

%         medis = mean(abs(dis)); vec=dis(indis{i}(:));
        medis = mean(abs(dis)); vec=dis(:);
        erm = sqrt(sum((vec).^2)/numel(vec));
        erms(i) =  erm;
        
        
        fprintf('Plano %i - Falta %f seg : \n',i,(size(X,2)-i)*toc)
    end
    fprintf([num2str(erms),'\n'])
end