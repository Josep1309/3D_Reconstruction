function Maps  = RegWcordtoImage(M,worldPoints,camSize)


Maps = zeros([camSize size(M,3) 3]);


for i = 1:size(M,3)

    [mat_int] = Adj2D_5thPol(worldPoints(:,1),M(:,1,i,1),M(:,2,i,1),1:camSize(2),1:camSize(1));
    Maps(:,:,i,1)  =  mat_int;

    [mat_int] = Adj2D_5thPol(worldPoints(:,2),M(:,1,i,1),M(:,2,i,1),1:camSize(2),1:camSize(1));
    Maps(:,:,i,2)  =  mat_int;

end

end


